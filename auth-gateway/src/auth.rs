use axum::{
    body::Body,
    extract::{Request, State},
    http::{header, Method, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::any,
};
use jsonwebtoken::{Algorithm, DecodingKey, Validation};
use matchit::Router;
use moka::future::Cache;
use redis::AsyncCommands;
use reqwest::Client as HttpClient;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tower_http::cors::{AllowOrigin, CorsLayer};
use tower_http::trace::TraceLayer;

#[derive(Clone, Debug)]
pub struct RouteConfig {
    pub feature: String,
    pub action: Option<String>, // NEW: view, edit, delete
    pub target: Option<String>,
}

#[derive(Clone)]
pub struct AppState {
    pub http_client: HttpClient,
    pub fga_client: OpenFgaClient,
    pub router: Arc<Router<RouteConfig>>,
    pub cache: Cache<(String, String), bool>,
    pub jwks_cache: Cache<String, DecodingKey>,
    pub jwks_url: String,
    pub zitadel_api_url: String,
    pub openfga_url: String,
    pub redis_client: redis::Client,
    pub upstream_url: String,
}

#[derive(Debug, Deserialize)]
struct Jwk {
    kid: String,
    n: String,
    e: String,
}

#[derive(Debug, Deserialize)]
struct Jwks {
    keys: Vec<Jwk>,
}

#[derive(Debug, Deserialize, Serialize)]
struct Claims {
    sub: String,
    exp: i64,
}

#[derive(Clone)]
pub struct OpenFgaClient {
    pub url: String,
    pub store_id: String,
}

impl OpenFgaClient {
    pub fn new(url: String, store_id: String) -> Self {
        Self { url, store_id }
    }
}

#[derive(Debug, Deserialize)]
struct AccessRule {
    path: String,
    #[allow(dead_code)]
    method: String,
    feature: String,
    action: Option<String>, // NEW: view, edit, delete
    target: Option<String>,
}

pub async fn load_access_rules(
    path: &str,
) -> Result<Arc<Router<RouteConfig>>, Box<dyn std::error::Error>> {
    let content = tokio::fs::read_to_string(path).await?;
    let rules: Vec<AccessRule> = serde_json::from_str(&content)?;

    let mut router = Router::new();
    for rule in rules {
        router.insert(
            &rule.path,
            RouteConfig {
                feature: rule.feature,
                action: rule.action, // Pass action from access rules
                target: rule.target,
            },
        )?;
    }

    Ok(Arc::new(router))
}

pub async fn auth_middleware(
    State(state): State<AppState>,
    mut req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let path = req.uri().path();

    // Check router for access rules
    let match_result = state.router.at(path);

    // Check if no route found
    if let Err(_) = match_result {
        tracing::warn!("No access rule found for path: {}", path);
        return Err(StatusCode::FORBIDDEN);
    };

    let matched = match_result.unwrap();
    let route_config = matched.value;

    // 1. Check if path has public_access feature
    if route_config.feature == "public_access" {
        tracing::debug!("Public access path, skipping auth/authz for: {}", path);
        return Ok(next.run(req).await);
    }

    // 2. Extract token
    let auth_header = req
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|h| h.to_str().ok())
        .and_then(|h| h.strip_prefix("Bearer "));

    let token = match auth_header {
        Some(t) => t,
        None => {
            tracing::warn!("Missing or invalid Authorization header");
            return Err(StatusCode::UNAUTHORIZED);
        }
    };

    // 3. Validate JWT
    let claims = match validate_jwt(&state, token).await {
        Ok(c) => c,
        Err(e) => {
            tracing::warn!("JWT validation failed: {:?}", e);
            return Err(StatusCode::UNAUTHORIZED);
        }
    };

    let user_id = &claims.sub;

    // 4. Rate Limiting (Redis-based, 100 req/min per user)
    if let Err(e) = check_rate_limit(&state, user_id).await {
        tracing::warn!("Rate limit exceeded for user {}: {:?}", user_id, e);
        return Err(StatusCode::TOO_MANY_REQUESTS);
    }

    // 5. Caching & OpenFGA Check
    let cache_key = (user_id.clone(), route_config.feature.clone());
    let cached_result = state.cache.get(&cache_key).await;

    let authorized = match cached_result {
        Some(result) => {
            tracing::debug!("Cache hit for {:?}", cache_key);
            result
        }
        None => {
            tracing::debug!("Cache miss for {:?}, checking OpenFGA", cache_key);
            let allowed = check_openfga_permission(
                &state.http_client,
                &state.fga_client,
                user_id,
                &route_config.feature,
                route_config.action.as_deref(), // NEW: Pass action
            )
            .await
            .unwrap_or(false);

            state.cache.insert(cache_key, allowed).await;
            allowed
        }
    };

    if !authorized {
        tracing::warn!(
            "User {} not authorized for feature {}",
            user_id,
            route_config.feature
        );
        return Err(StatusCode::FORBIDDEN);
    }

    // 6. Inject User ID in header for upstream
    req.headers_mut()
        .insert("X-User-ID", user_id.parse().unwrap());

    Ok(next.run(req).await)
}

async fn validate_jwt(
    state: &AppState,
    token: &str,
) -> Result<Claims, jsonwebtoken::errors::Error> {
    let header = jsonwebtoken::decode_header(token)?;
    let kid = header
        .kid
        .ok_or(jsonwebtoken::errors::ErrorKind::InvalidToken)?;

    let decoding_key = match state.jwks_cache.get(&kid).await {
        Some(key) => key,
        None => {
            let jwks: Jwks = state
                .http_client
                .get(&state.jwks_url)
                .send()
                .await
                .map_err(|_| jsonwebtoken::errors::ErrorKind::InvalidToken)?
                .json()
                .await
                .map_err(|_| jsonwebtoken::errors::ErrorKind::InvalidToken)?;

            let jwk = jwks
                .keys
                .into_iter()
                .find(|k| k.kid == kid)
                .ok_or(jsonwebtoken::errors::ErrorKind::InvalidToken)?;

            let key = DecodingKey::from_rsa_components(&jwk.n, &jwk.e)?;
            state.jwks_cache.insert(kid.clone(), key.clone()).await;
            key
        }
    };

    let mut validation = Validation::new(Algorithm::RS256);
    validation.validate_exp = true;

    jsonwebtoken::decode::<Claims>(token, &decoding_key, &validation).map(|data| data.claims)
}

async fn check_rate_limit(
    state: &AppState,
    user_id: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut conn = state
        .redis_client
        .get_multiplexed_async_connection()
        .await?;
    let key = format!("rate_limit:{}", user_id);

    let current: i32 = conn.get(&key).await.unwrap_or(0);

    if current >= 100 {
        return Err("Rate limit exceeded".into());
    }

    redis::pipe()
        .atomic()
        .incr(&key, 1)
        .expire(&key, 60)
        .query_async::<()>(&mut conn)
        .await?;

    Ok(())
}

async fn check_openfga_permission(
    client: &HttpClient,
    fga_client: &OpenFgaClient,
    user_id: &str,
    feature: &str,
    action: Option<&str>, // NEW: action parameter
) -> Result<bool, Box<dyn std::error::Error>> {
    let check_url = format!("{}/stores/{}/check", fga_client.url, fga_client.store_id);

    // Use action as relation if provided, default to "viewer" for backward compatibility
    let relation = action.unwrap_or("viewer");

    let request_body = serde_json::json!({
        "tuple_key": {
            "user": format!("user:{}", user_id),
            "relation": relation,  // Use action/relation
            "object": format!("feature:{}", feature),
        }
    });

    // Send request and handle errors gracefully
    match client.post(&check_url).json(&request_body).send().await {
        Ok(response) if response.status().is_success() => {
            let result: serde_json::Value = response.json().await?;
            Ok(result["allowed"].as_bool().unwrap_or(false))
        }
        Ok(response) => {
            let status = response.status(); // Capture before consuming
            let error = response.text().await.unwrap_or_default();
            tracing::warn!("OpenFGA check failed with status {}: {}", status, error);
            Ok(false)
        }
        Err(e) => {
            tracing::warn!("OpenFGA request failed: {}", e);
            Ok(false)
        }
    }
}

pub fn create_router(state: AppState, allowed_origins: Vec<header::HeaderValue>) -> axum::Router {
    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list(allowed_origins))
        .allow_methods([
            Method::GET,
            Method::POST,
            Method::PUT,
            Method::DELETE,
            Method::OPTIONS,
        ])
        .allow_headers([
            header::AUTHORIZATION,
            header::CONTENT_TYPE,
            header::HeaderName::from_static("x-user-id"),
            header::HeaderName::from_static("x-gateway-secret"),
        ])
        .allow_credentials(true);

    // Create separate router for webhooks (no auth middleware)
    let webhook_routes = axum::Router::new()
        .route(
            "/webhooks/user-created",
            axum::routing::post(crate::webhooks::handle_user_created),
        )
        .route(
            "/webhooks/user-updated",
            axum::routing::post(crate::webhooks::handle_user_updated),
        )
        .route(
            "/webhooks/user-deleted",
            axum::routing::post(crate::webhooks::handle_user_deleted),
        )
        .with_state(state.clone());

    // Main router with auth middleware
    let protected_routes = axum::Router::new()
        .route("/*path", any(proxy_handler))
        .route_layer(middleware::from_fn_with_state(
            state.clone(),
            auth_middleware,
        ))
        .with_state(state);

    // Merge routers
    axum::Router::new()
        .merge(webhook_routes)
        .merge(protected_routes)
        .layer(TraceLayer::new_for_http())
        .layer(cors)
}

pub async fn proxy_handler(
    State(state): State<AppState>,
    req: Request<Body>,
) -> Result<Response<Body>, StatusCode> {
    let path = req.uri().path();
    let query = req.uri().query().unwrap_or("");

    // Get the route config to determine target
    let match_result = state.router.at(path);
    let target_url = if let Ok(matched) = match_result {
        let route_config = matched.value;
        match &route_config.target {
            Some(target) if target == "zitadel" => {
                format!("{}{}", state.zitadel_api_url, path)
            }
            Some(target) if target == "openfga" => {
                format!("{}{}", state.openfga_url, path)
            }
            _ => {
                format!("{}{}", state.upstream_url, path)
            }
        }
    } else {
        format!("{}{}", state.upstream_url, path)
    };

    let final_url = if query.is_empty() {
        target_url
    } else {
        format!("{}?{}", target_url, query)
    };

    tracing::debug!("Proxying to: {}", final_url);

    let method = req.method().clone();
    let headers = req.headers().clone();
    let body_bytes = axum::body::to_bytes(req.into_body(), usize::MAX)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut proxy_req = state.http_client.request(method, &final_url);

    for (name, value) in headers.iter() {
        if name != header::HOST {
            proxy_req = proxy_req.header(name, value);
        }
    }

    if !body_bytes.is_empty() {
        proxy_req = proxy_req.body(body_bytes.to_vec());
    }

    let proxy_response = proxy_req.send().await.map_err(|e| {
        tracing::error!("Proxy request failed: {}", e);
        StatusCode::BAD_GATEWAY
    })?;

    let status = proxy_response.status();
    let headers = proxy_response.headers().clone();
    let response_bytes = proxy_response
        .bytes()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;

    let mut response = Response::builder().status(status);

    for (name, value) in headers.iter() {
        response = response.header(name, value);
    }

    response
        .body(Body::from(response_bytes))
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}

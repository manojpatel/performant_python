use auth_gateway::auth::{create_router, AppState, OpenFgaClient};
use axum::{
    body::Body,
    http::{header, Method, Request, StatusCode},
};
use matchit::Router;
use moka::future::Cache;
use redis::Client as RedisClient;
use std::sync::Arc;
// use tower::Service removed
use tower::ServiceExt; // for `oneshot`

#[tokio::test]
async fn test_cors_configuration() {
    // 1. Setup Mock State
    let http_client = reqwest::Client::new();
    let fga_client = OpenFgaClient::new("http://openfga:8080".into(), "dummy-store-id".into());
    let router = Arc::new(Router::new());

    // We don't need real redis/cache for CORS options check generally,
    // but the app state build needs them.
    // For unit testing, mocking would be better, but we need to supply valid structs.
    // Redis client is just a client handle, doesn't connect immediately usually unless we call get_connection.
    // But main() calls config check.

    // Redis Client
    let redis_client = RedisClient::open("redis://127.0.0.1/").unwrap();

    let state = AppState {
        http_client,
        fga_client,
        router,
        cache: Cache::new(10),
        jwks_cache: Cache::new(10),
        jwks_url: "http://jwks".into(),
        zitadel_api_url: "http://zitadel".into(),
        openfga_url: "http://openfga:8080".into(),
        redis_client,
        upstream_url: "http://upstream".into(),
    };

    // 2. Define Allowed Origins
    let allowed_origin = "http://localhost:3000"
        .parse::<header::HeaderValue>()
        .unwrap();
    let allowed_origins = vec![allowed_origin.clone()];

    // 3. Create Router
    let app = create_router(state.clone(), allowed_origins);

    // 4. Test OPTIONS request with Allowed Origin
    let req = Request::builder()
        .method(Method::OPTIONS)
        .uri("/some/path")
        .header(header::ORIGIN, "http://localhost:3000")
        .header(header::ACCESS_CONTROL_REQUEST_METHOD, "GET")
        .body(Body::empty())
        .unwrap();

    let response = app.oneshot(req).await.unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        response.headers().get(header::ACCESS_CONTROL_ALLOW_ORIGIN),
        Some(&allowed_origin)
    );

    // 5. Test OPTIONS request with Disallowed Origin
    let app = create_router(state, vec![allowed_origin.clone()]); // recreate to be safe/clean
    let req = Request::builder()
        .method(Method::OPTIONS)
        .uri("/some/path")
        .header(header::ORIGIN, "http://evil.com")
        .header(header::ACCESS_CONTROL_REQUEST_METHOD, "GET")
        .body(Body::empty())
        .unwrap();

    let response = app.oneshot(req).await.unwrap();

    // If origin is not allowed, CORS middleware usually does not set the AC-Allow-Origin header
    // or returns 200 but without the header.
    // Tower-http validation: if origin doesn't match, it doesn't send the header.
    assert_eq!(response.status(), StatusCode::OK); // Options usually returns OK
    assert_eq!(
        response.headers().get(header::ACCESS_CONTROL_ALLOW_ORIGIN),
        None
    );
}

use auth_gateway::auth;

use auth::{AppState, OpenFgaClient};
use axum::http::header;
use moka::future::Cache;
use reqwest::Client as HttpClient;
use std::net::SocketAddr;
use std::time::Duration;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() {
    // Initialize dotenv
    dotenv::dotenv().ok();

    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "auth_gateway=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Initialize clients
    let http_client = HttpClient::new();
    let fga_url = std::env::var("OPENFGA_URL").expect("OPENFGA_URL must be set");
    let fga_store_id = std::env::var("OPENFGA_STORE_ID").expect("OPENFGA_STORE_ID must be set");
    let fga_client = OpenFgaClient::new(fga_url.clone(), fga_store_id.clone());
    let issuer_url = std::env::var("ZITADEL_ISSUER_URL").expect("ZITADEL_ISSUER_URL must be set");
    let jwks_url = format!("{}/oauth/v2/keys", issuer_url);
    let zitadel_api_url = std::env::var("ZITADEL_API_URL").expect("ZITADEL_API_URL must be set");

    let upstream_url =
        std::env::var("UPSTREAM_URL").unwrap_or_else(|_| "http://localhost:8000".to_string());

    // Initialize Redis (Valkey)
    let redis_url = std::env::var("REDIS_URL").expect("REDIS_URL must be set");
    let redis_client = redis::Client::open(redis_url).expect("Invalid Redis URL");

    // Initialize Cache (30s TTL)
    let cache = Cache::builder()
        .time_to_live(Duration::from_secs(30))
        .build();

    let jwks_cache = Cache::builder()
        .time_to_live(Duration::from_secs(24 * 60 * 60))
        .build();

    // Run feature migration BEFORE loading new rules
    // This ensures OpenFGA tuples are updated when features are renamed/deleted
    tracing::info!("Running feature migration check...");
    if let Err(e) = auth_gateway::feature_sync::migrate_features(
        &http_client,
        &fga_url,
        &fga_store_id.clone(),
        "access_rules.json",      // Latest rules
        "access_rules_prev.json", // Previous rules (from CI/CD)
    )
    .await
    {
        tracing::error!("Feature migration failed: {}", e);
        // Continue anyway - migration failure shouldn't block startup
    }

    // Load access rules (from latest version)
    let router = auth::load_access_rules("access_rules.json")
        .await
        .expect("Failed to load access rules");

    let state = AppState {
        http_client,
        fga_client,
        router,
        cache,
        jwks_cache,
        jwks_url,
        zitadel_api_url,
        openfga_url: fga_url,
        redis_client,
        upstream_url,
    };

    // Configure CORS
    let allowed_origins_str = std::env::var("ALLOWED_ORIGINS")
        .unwrap_or_else(|_| "http://localhost:3000,http://localhost:8080".to_string());

    let allowed_origins: Vec<header::HeaderValue> = allowed_origins_str
        .split(',')
        .map(|s| {
            s.trim()
                .parse::<header::HeaderValue>()
                .expect("Invalid origin header value")
        })
        .collect();

    // Build app with routes using helper function (for testability)
    let app = auth::create_router(state, allowed_origins);

    // Run the server
    let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
    tracing::info!("listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

// function content moved to auth.rs

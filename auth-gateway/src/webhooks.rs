// Webhook Handlers for Zitadel User Sync
// Handles incoming webhooks from Zitadel Actions to sync users to OpenFGA

use axum::{extract::State, http::StatusCode, Json};
use serde::{Deserialize, Serialize};

use crate::auth::AppState;

// ============================================================================
// Event Types
// ============================================================================

#[derive(Debug, Deserialize)]
pub struct UserCreatedEvent {
    #[serde(rename = "userId")]
    pub user_id: String,
    #[serde(rename = "userName")]
    pub user_name: String,
    #[serde(rename = "userType")]
    pub user_type: Option<String>, // "human" or "machine"
}

#[derive(Debug, Deserialize)]
pub struct UserUpdatedEvent {
    #[serde(rename = "userId")]
    pub user_id: String,
    #[serde(rename = "userName")]
    pub user_name: String,
}

#[derive(Debug, Deserialize)]
pub struct UserDeletedEvent {
    #[serde(rename = "userId")]
    pub user_id: String,
}

#[derive(Debug, Serialize)]
pub struct WebhookResponse {
    pub status: String,
    pub message: String,
}

// ============================================================================
// Webhook Handlers
// ============================================================================

/// Handle user creation event from Zitadel
///
/// Creates a user entity in OpenFGA so that the admin can see all users
/// and assign permissions via the admin UI.
///
/// This creates a tuple: `user:{userId}` is `member` of `organization:users`
/// This allows admin tools to query all users from OpenFGA.
///
/// **No permissions are assigned** - only the user entity is registered.
/// Admin assigns permissions separately via the admin interface.
pub async fn handle_user_created(
    State(state): State<AppState>,
    Json(event): Json<UserCreatedEvent>,
) -> Result<Json<WebhookResponse>, StatusCode> {
    tracing::info!(
        "Webhook: User created - ID: {}, Name: {}, Type: {:?}",
        event.user_id,
        event.user_name,
        event.user_type
    );

    let store_id =
        std::env::var("OPENFGA_STORE_ID").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Create a tuple to register the user entity in OpenFGA
    // This doesn't grant any permissions - it just makes the user visible to admin tools
    let tuple = serde_json::json!({
        "user": format!("user:{}", event.user_id),
        "relation": "member",
        "object": "organization:users"
    });

    let write_request = serde_json::json!({
        "writes": {
            "tuple_keys": [tuple]
        }
    });

    match state
        .http_client
        .post(format!("{}/stores/{}/write", state.openfga_url, store_id))
        .json(&write_request)
        .send()
        .await
    {
        Ok(resp) if resp.status().is_success() => {
            tracing::info!("Registered user {} in OpenFGA", event.user_id);
            Ok(Json(WebhookResponse {
                status: "success".to_string(),
                message: format!(
                    "User {} registered in OpenFGA. Admin can now assign permissions.",
                    event.user_id
                ),
            }))
        }
        Ok(resp) => {
            let error: String = resp.text().await.unwrap_or_default();
            tracing::error!("Failed to register user in OpenFGA: {}", error);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
        Err(e) => {
            tracing::error!("OpenFGA request failed: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Handle user update event from Zitadel
///
/// Currently logs the event (extend as needed for role changes, etc.)
pub async fn handle_user_updated(
    State(_state): State<AppState>,
    Json(event): Json<UserUpdatedEvent>,
) -> Result<Json<WebhookResponse>, StatusCode> {
    tracing::info!(
        "Webhook: User updated - ID: {}, Name: {}",
        event.user_id,
        event.user_name
    );

    // Future: Handle role/permission updates
    // For now, just acknowledge the event

    Ok(Json(WebhookResponse {
        status: "acknowledged".to_string(),
        message: format!("User {} update acknowledged", event.user_id),
    }))
}

/// Handle user deletion event from Zitadel
///
/// Removes all OpenFGA tuples associated with the user
pub async fn handle_user_deleted(
    State(state): State<AppState>,
    Json(event): Json<UserDeletedEvent>,
) -> Result<Json<WebhookResponse>, StatusCode> {
    tracing::info!("Webhook: User deleted - ID: {}", event.user_id);

    let store_id =
        std::env::var("OPENFGA_STORE_ID").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Read tuples filtered by user (much more efficient than reading all tuples!)
    let read_url = format!("{}/stores/{}/read", state.openfga_url, store_id);
    let user_string = format!("user:{}", event.user_id);

    let read_request = serde_json::json!({
        "tuple_key": {
            "user": user_string
        }
    });

    tracing::debug!("Querying OpenFGA for tuples of user: {}", event.user_id);

    let read_response = match state
        .http_client
        .post(&read_url)
        .json(&read_request)
        .send()
        .await
    {
        Ok(resp) if resp.status().is_success() => resp,
        Ok(resp) => {
            let error: String = resp.text().await.unwrap_or_default();
            tracing::error!("Failed to read tuples from OpenFGA: {}", error);
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
        Err(e) => {
            tracing::error!("OpenFGA read request failed: {}", e);
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    // Use same deserialization pattern as feature_sync (no clone!)
    #[derive(serde::Deserialize)]
    struct ReadResponse {
        tuples: Vec<serde_json::Value>,
    }

    let read_result: ReadResponse = read_response
        .json()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if read_result.tuples.is_empty() {
        tracing::info!("No tuples found for user {}", event.user_id);
        return Ok(Json(WebhookResponse {
            status: "success".to_string(),
            message: format!("User {} had no permissions to clean up", event.user_id),
        }));
    }

    tracing::info!(
        "Found {} tuples to delete for user {}",
        read_result.tuples.len(),
        event.user_id
    );

    // Batch delete ALL tuples in a single API call
    let delete_keys: Vec<&serde_json::Value> =
        read_result.tuples.iter().map(|t| &t["key"]).collect();

    let delete_url = format!("{}/stores/{}/write", state.openfga_url, store_id);
    let delete_request = serde_json::json!({
        "deletes": {
            "tuple_keys": delete_keys
        }
    });

    match state
        .http_client
        .post(&delete_url)
        .json(&delete_request)
        .send()
        .await
    {
        Ok(resp) if resp.status().is_success() => {
            tracing::info!(
                "Cleaned up {} tuples for user {} in single batch",
                read_result.tuples.len(),
                event.user_id
            );
            Ok(Json(WebhookResponse {
                status: "success".to_string(),
                message: format!(
                    "User {} deleted: cleaned up {} permissions",
                    event.user_id,
                    read_result.tuples.len()
                ),
            }))
        }
        Ok(resp) => {
            let error: String = resp.text().await.unwrap_or_default();
            tracing::error!("Failed to delete tuples: {}", error);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
        Err(e) => {
            tracing::error!("OpenFGA delete request failed: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

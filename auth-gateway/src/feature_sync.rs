// Feature Sync Module
// Handles automatic migration of OpenFGA tuples when access_rules.json changes

use anyhow::Result;
use reqwest::Client as HttpClient;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AccessRule {
    pub path: String,
    pub method: String,
    pub feature: String,
    pub target: Option<String>,
}

/// Migrate features based on changes between two access_rules files
pub async fn migrate_features(
    http_client: &HttpClient,
    openfga_url: &str,
    store_id: &str,
    latest_path: &str,
    prev_path: &str,
) -> Result<()> {
    tracing::info!(
        "Checking for feature changes between {} and {}",
        latest_path,
        prev_path
    );

    // Load both versions
    let latest_rules = load_rules(latest_path)?;
    let prev_rules = match load_rules(prev_path) {
        Ok(rules) => rules,
        Err(e) => {
            tracing::warn!("Could not load previous rules ({}), skipping migration", e);
            return Ok(());
        }
    };

    // Extract features
    let latest_features = extract_features(&latest_rules);
    let prev_features = extract_features(&prev_rules);

    // Detect changes
    let renamed = detect_renames(&prev_rules, &latest_rules);
    let deleted = detect_deletions(&prev_features, &latest_features);
    let added = detect_additions(&prev_features, &latest_features);

    // Log summary
    if renamed.is_empty() && deleted.is_empty() && added.is_empty() {
        tracing::info!("No feature changes detected");
        return Ok(());
    }

    tracing::info!("Feature changes detected:");
    if !renamed.is_empty() {
        tracing::info!("  Renamed: {:?}", renamed);
    }
    if !deleted.is_empty() {
        tracing::info!("  Deleted: {:?}", deleted);
    }
    if !added.is_empty() {
        tracing::info!("  Added: {:?}", added);
    }

    // Collect features that need tuple migration (old feature names for renames, deleted features)
    let mut features_to_fetch: Vec<String> = Vec::new();

    // Add old feature names from renames
    for (old_feature, _) in &renamed {
        features_to_fetch.push(old_feature.clone());
    }

    // Add deleted features
    features_to_fetch.extend(deleted.clone());

    // Fetch tuples ONLY for features being migrated/deleted (not all millions of tuples!)
    let relevant_tuples = if !features_to_fetch.is_empty() {
        fetch_tuples_for_features(http_client, openfga_url, store_id, &features_to_fetch).await?
    } else {
        vec![]
    };

    // Apply ALL migrations in a SINGLE batched call
    if !renamed.is_empty() {
        migrate_all_feature_tuples(
            http_client,
            openfga_url,
            store_id,
            &renamed,
            &relevant_tuples,
        )
        .await?;
    }

    // Apply ALL deletions in a SINGLE batched call
    if !deleted.is_empty() {
        cleanup_all_feature_tuples(
            http_client,
            openfga_url,
            store_id,
            &deleted,
            &relevant_tuples,
        )
        .await?;
    }

    tracing::info!("Feature migration completed successfully");
    Ok(())
}

fn load_rules(path: &str) -> Result<Vec<AccessRule>> {
    let content = fs::read_to_string(path)?;
    let rules: Vec<AccessRule> = serde_json::from_str(&content)?;
    Ok(rules)
}

fn extract_features(rules: &[AccessRule]) -> HashSet<String> {
    rules
        .iter()
        .map(|r| r.feature.clone())
        .filter(|f| f != "public_access") // Ignore public_access
        .collect()
}

fn detect_renames(prev: &[AccessRule], latest: &[AccessRule]) -> Vec<(String, String)> {
    let mut renames = Vec::new();

    // Heuristic: same path+method but different feature = likely a rename
    for prev_rule in prev {
        if prev_rule.feature == "public_access" {
            continue;
        }

        for latest_rule in latest {
            if latest_rule.feature == "public_access" {
                continue;
            }

            // If same endpoint but different feature, it's likely renamed
            if prev_rule.path == latest_rule.path
                && prev_rule.method == latest_rule.method
                && prev_rule.feature != latest_rule.feature
            {
                renames.push((prev_rule.feature.clone(), latest_rule.feature.clone()));
            }
        }
    }

    // Deduplicate
    renames.sort();
    renames.dedup();
    renames
}

fn detect_deletions(
    prev_features: &HashSet<String>,
    latest_features: &HashSet<String>,
) -> Vec<String> {
    prev_features.difference(latest_features).cloned().collect()
}

fn detect_additions(
    prev_features: &HashSet<String>,
    latest_features: &HashSet<String>,
) -> Vec<String> {
    latest_features.difference(prev_features).cloned().collect()
}

/// Fetch tuples for specific features only (much more efficient than fetching all!)
async fn fetch_tuples_for_features(
    client: &HttpClient,
    openfga_url: &str,
    store_id: &str,
    features: &[String],
) -> Result<Vec<serde_json::Value>> {
    if features.is_empty() {
        return Ok(vec![]);
    }

    tracing::debug!(
        "Fetching tuples for {} specific features from OpenFGA",
        features.len()
    );

    let read_url = format!("{}/stores/{}/read", openfga_url, store_id);

    #[derive(serde::Deserialize)]
    struct ReadResponse {
        tuples: Vec<serde_json::Value>,
    }

    let mut all_tuples = Vec::new();

    // Fetch tuples for each feature
    for feature in features {
        let read_request = serde_json::json!({
            "tuple_key": {
                "object": format!("feature:{}", feature)
            }
        });

        match client.post(&read_url).json(&read_request).send().await {
            Ok(response) if response.status().is_success() => {
                let result: ReadResponse = response.json().await?;
                all_tuples.extend(result.tuples);
            }
            Ok(response) => {
                let error = response.text().await.unwrap_or_default();
                tracing::warn!("Failed to fetch tuples for feature {}: {}", feature, error);
            }
            Err(e) => {
                tracing::warn!("Request failed for feature {}: {}", feature, e);
            }
        }
    }

    tracing::debug!(
        "Fetched {} tuples for {} features",
        all_tuples.len(),
        features.len()
    );
    Ok(all_tuples)
}

/// Migrate ALL feature renames in a single batched API call
async fn migrate_all_feature_tuples(
    client: &HttpClient,
    openfga_url: &str,
    store_id: &str,
    renames: &[(String, String)],
    all_tuples: &[serde_json::Value],
) -> Result<()> {
    tracing::info!(
        "Migrating {} feature renames in single batch",
        renames.len()
    );

    let mut all_deletes = Vec::new();
    let mut all_writes = Vec::new();
    let mut total_tuples = 0;

    // Process ALL renames and build combined deletes/writes
    for (old_feature, new_feature) in renames {
        tracing::debug!("Processing rename: {} → {}", old_feature, new_feature);

        // Filter tuples for this specific rename
        let tuples_to_migrate: Vec<&serde_json::Value> = all_tuples
            .iter()
            .filter(|t| t["key"]["object"].as_str() == Some(old_feature.as_str()))
            .collect();

        if tuples_to_migrate.is_empty() {
            tracing::debug!("No tuples found for feature: {}", old_feature);
            continue;
        }

        tracing::debug!(
            "Found {} tuples for {} → {}",
            tuples_to_migrate.len(),
            old_feature,
            new_feature
        );
        total_tuples += tuples_to_migrate.len();

        // Add to combined batch
        for tuple in tuples_to_migrate {
            let user = tuple["key"]["user"].as_str().unwrap();
            let relation = tuple["key"]["relation"].as_str().unwrap();

            all_deletes.push(serde_json::json!({
                "user": user,
                "relation": relation,
                "object": old_feature
            }));

            all_writes.push(serde_json::json!({
                "user": user,
                "relation": relation,
                "object": new_feature
            }));
        }
    }

    if all_deletes.is_empty() {
        tracing::info!("No tuples to migrate across all renames");
        return Ok(());
    }

    // Send ONE MASSIVE batched request for ALL renames
    tracing::info!(
        "Sending batch migration: {} tuples across {} renames",
        total_tuples,
        renames.len()
    );

    let write_url = format!("{}/stores/{}/write", openfga_url, store_id);
    let result = client
        .post(&write_url)
        .json(&serde_json::json!({
            "deletes": {
                "tuple_keys": all_deletes
            },
            "writes": {
                "tuple_keys": all_writes
            }
        }))
        .send()
        .await?;

    if result.status().is_success() {
        tracing::info!(
            "✅ Successfully migrated {} tuples across {} renames in single batch!",
            total_tuples,
            renames.len()
        );
    } else {
        let error_text = result.text().await?;
        tracing::error!("Failed to migrate tuples: {}", error_text);
        return Err(anyhow::anyhow!("Batch migration failed: {}", error_text));
    }

    Ok(())
}

/// Cleanup ALL deleted features in a single batched API call
async fn cleanup_all_feature_tuples(
    client: &HttpClient,
    openfga_url: &str,
    store_id: &str,
    deleted_features: &[String],
    all_tuples: &[serde_json::Value],
) -> Result<()> {
    tracing::info!(
        "Cleaning up {} deleted features in single batch",
        deleted_features.len()
    );

    let mut all_delete_keys = Vec::new();
    let mut total_tuples = 0;

    // Process ALL deletions and build combined delete list
    for feature in deleted_features {
        tracing::debug!("Processing deletion: {}", feature);

        // Filter tuples for this feature
        let tuples_to_delete: Vec<&serde_json::Value> = all_tuples
            .iter()
            .filter(|t| t["key"]["object"].as_str() == Some(feature.as_str()))
            .collect();

        if tuples_to_delete.is_empty() {
            tracing::debug!("No tuples found for deleted feature: {}", feature);
            continue;
        }

        tracing::debug!(
            "Found {} tuples for deleted feature: {}",
            tuples_to_delete.len(),
            feature
        );
        total_tuples += tuples_to_delete.len();

        // Add to combined delete batch
        for tuple in tuples_to_delete {
            all_delete_keys.push(&tuple["key"]);
        }
    }

    if all_delete_keys.is_empty() {
        tracing::info!("No tuples to delete across all deleted features");
        return Ok(());
    }

    // Send ONE MASSIVE batched delete for ALL deleted features
    tracing::info!(
        "Sending batch cleanup: {} tuples across {} deleted features",
        total_tuples,
        deleted_features.len()
    );

    let write_url = format!("{}/stores/{}/write", openfga_url, store_id);
    let result = client
        .post(&write_url)
        .json(&serde_json::json!({
            "deletes": {
                "tuple_keys": all_delete_keys
            }
        }))
        .send()
        .await?;

    if result.status().is_success() {
        tracing::info!(
            "✅ Successfully cleaned up {} tuples across {} deleted features in single batch!",
            total_tuples,
            deleted_features.len()
        );
    } else {
        let error_text = result.text().await?;
        tracing::error!("Failed to cleanup tuples: {}", error_text);
        return Err(anyhow::anyhow!("Batch cleanup failed: {}", error_text));
    }

    Ok(())
}

#!/bin/bash
# MongoDB Initialization Script
# This script runs automatically when MongoDB container starts for the first time

set -e

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Initializing MongoDB...${NC}"

# Get credentials from environment variables (passed by docker-compose)
MONGO_ROOT_USER=${MONGO_INITDB_ROOT_USERNAME:-admin}
MONGO_ROOT_PASSWORD=${MONGO_INITDB_ROOT_PASSWORD:-changeme}
MONGO_DBNAME=${MONGO_INITDB_DATABASE:-crypto_trade_hub}

# Create initial database and indexes
mongosh --username "$MONGO_ROOT_USER" --password "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin <<MONGO_SCRIPT
  // Switch to target database
  use $MONGO_DBNAME

  // Create collections with validation schemas
  db.createCollection("users", {
    validator: {
      \$jsonSchema: {
        bsonType: "object",
        required: ["email", "created_at"],
        properties: {
          _id: { bsonType: "objectId" },
          email: { bsonType: "string", pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$" },
          hashed_password: { bsonType: "string" },
          name: { bsonType: "string" },
          is_active: { bsonType: "bool" },
          is_superuser: { bsonType: "bool" },
          plan: { bsonType: "string", enum: ["starter", "pro", "premium", "enterprise"] },
          activation_credits: { bsonType: "int" },
          activation_credits_used: { bsonType: "int" },
          created_at: { bsonType: "date" },
          updated_at: { bsonType: "date" }
        }
      }
    }
  })

  db.createCollection("bots", {
    validator: {
      \$jsonSchema: {
        bsonType: "object",
        required: ["user_id", "name"],
        properties: {
          _id: { bsonType: "objectId" },
          user_id: { bsonType: "objectId" },
          name: { bsonType: "string" },
          is_active_slot: { bsonType: "bool" },
          is_running: { bsonType: "bool" },
          swap_count: { bsonType: "int" },
          swap_history: { bsonType: "array" },
          created_at: { bsonType: "date" }
        }
      }
    }
  })

  db.createCollection("audit_logs")

  // Create indexes for performance
  
  // Users indexes
  db.users.createIndex({ "email": 1 }, { unique: true })
  db.users.createIndex({ "google_id": 1 }, { sparse: true, unique: true })
  db.users.createIndex({ "created_at": -1 })
  db.users.createIndex({ "is_active": 1 })
  
  // Bots indexes
  db.bots.createIndex({ "user_id": 1 })
  db.bots.createIndex({ "user_id": 1, "is_active_slot": 1 })
  db.bots.createIndex({ "user_id": 1, "is_running": 1 })
  db.bots.createIndex({ "created_at": -1 })
  
  // Audit logs indexes
  db.audit_logs.createIndex({ "user_id": 1 })
  db.audit_logs.createIndex({ "event_type": 1 })
  db.audit_logs.createIndex({ "timestamp": -1 })
  db.audit_logs.createIndex({ "severity": 1 })
  
  // TTL index for old audit logs (keep only 90 days)
  db.audit_logs.createIndex({ "timestamp": 1 }, { expireAfterSeconds: 7776000 })

  // Set up text search indexes
  db.bots.createIndex({ "name": "text", "description": "text" })
  db.users.createIndex({ "name": "text", "email": "text" })

  // Print confirmation
  print("✓ Collections created")
  print("✓ Indexes created")
  print("✓ MongoDB initialization complete")

MONGO_SCRIPT

echo -e "${GREEN}MongoDB initialized successfully!${NC}"

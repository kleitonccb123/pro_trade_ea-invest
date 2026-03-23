// MongoDB initialization script
// This script runs on first container startup

// Use the main database
db = db.getSiblingDB('crypto_trade_hub');

// Create collections with schema validation
db.createCollection('users', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['email', 'hashed_password', 'created_at'],
            properties: {
                email: {
                    bsonType: 'string',
                    description: 'User email - required'
                },
                hashed_password: {
                    bsonType: 'string',
                    description: 'Hashed password - required'
                },
                name: {
                    bsonType: 'string'
                },
                is_active: {
                    bsonType: 'bool'
                },
                is_admin: {
                    bsonType: 'bool'
                },
                two_factor_enabled: {
                    bsonType: 'bool'
                },
                created_at: {
                    bsonType: 'date'
                },
                updated_at: {
                    bsonType: 'date'
                }
            }
        }
    }
});

db.createCollection('trade_logs', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['user_id', 'exchange', 'symbol', 'side', 'quantity', 'price', 'timestamp'],
            properties: {
                user_id: { bsonType: 'string' },
                exchange: { bsonType: 'string' },
                symbol: { bsonType: 'string' },
                side: { enum: ['buy', 'sell'] },
                quantity: { bsonType: 'double' },
                price: { bsonType: 'double' },
                fee: { bsonType: 'double' },
                order_id: { bsonType: 'string' },
                robot_id: { bsonType: 'string' },
                strategy_type: { bsonType: 'string' },
                timestamp: { bsonType: 'date' }
            }
        }
    }
});

db.createCollection('robots');
db.createCollection('api_credentials');
db.createCollection('sessions');
db.createCollection('pnl_history');
db.createCollection('audit_events');
db.createCollection('strategies');
db.createCollection('licenses');
db.createCollection('affiliates');
db.createCollection('notifications');

// Create indexes for performance
print('Creating indexes...');

// Users indexes
db.users.createIndex({ 'email': 1 }, { unique: true });
db.users.createIndex({ 'google_id': 1 }, { sparse: true });
db.users.createIndex({ 'created_at': -1 });

// Trade logs indexes (critical for PnL queries)
db.trade_logs.createIndex({ 'user_id': 1, 'timestamp': -1 });
db.trade_logs.createIndex({ 'user_id': 1, 'symbol': 1, 'timestamp': -1 });
db.trade_logs.createIndex({ 'robot_id': 1, 'timestamp': -1 });
db.trade_logs.createIndex({ 'exchange': 1, 'timestamp': -1 });

// Robots indexes
db.robots.createIndex({ 'user_id': 1 });
db.robots.createIndex({ 'status': 1 });
db.robots.createIndex({ 'exchange': 1, 'symbol': 1 });

// Sessions indexes
db.sessions.createIndex({ 'user_id': 1 });
db.sessions.createIndex({ 'token_hash': 1 }, { unique: true });
db.sessions.createIndex({ 'expires_at': 1 }, { expireAfterSeconds: 0 }); // TTL index

// PnL history indexes
db.pnl_history.createIndex({ 'user_id': 1, 'timestamp': -1 });
db.pnl_history.createIndex({ 'symbol': 1, 'timestamp': -1 });

// API credentials indexes
db.api_credentials.createIndex({ 'user_id': 1, 'exchange': 1 });

// Audit events indexes
db.audit_events.createIndex({ 'user_id': 1, 'timestamp': -1 });
db.audit_events.createIndex({ 'event_type': 1, 'timestamp': -1 });

// Licenses indexes
db.licenses.createIndex({ 'user_id': 1 });
db.licenses.createIndex({ 'license_key': 1 }, { unique: true, sparse: true });
db.licenses.createIndex({ 'expires_at': 1 });

// Affiliates indexes
db.affiliates.createIndex({ 'user_id': 1 }, { unique: true });
db.affiliates.createIndex({ 'referral_code': 1 }, { unique: true });

// Notifications indexes
db.notifications.createIndex({ 'user_id': 1, 'read': 1, 'created_at': -1 });
db.notifications.createIndex({ 'created_at': -1 });

print('MongoDB initialization complete!');
print('Collections created: users, trade_logs, robots, api_credentials, sessions, pnl_history, audit_events, strategies, licenses, affiliates, notifications');

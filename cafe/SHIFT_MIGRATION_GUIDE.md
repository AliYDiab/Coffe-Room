# Shift Management Migration Guide
# This file contains all database schema and firebase sync changes
# Apply these changes to BOTH desktop (Python) and mobile apps

## ============================================
# DATABASE SCHEMA CHANGES
## ============================================

### 1. NEW TABLE: cashiers
# Desktop (SQLite):
CREATE TABLE IF NOT EXISTS cashiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

# Mobile (Firebase/Firestore):
# Collection: "cashiers"
# Document structure:
{
    "name": "string (required)",
    "active": "boolean (default: true)",
    "created_at": "timestamp (server timestamp)",
    "updated_at": "timestamp"
}

### 2. NEW TABLE: shifts
# Desktop (SQLite):
CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cashier_id INTEGER NOT NULL,
    shift_type TEXT NOT NULL CHECK(shift_type IN ('morning', 'night')),
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed')),
    total_sales REAL DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(cashier_id) REFERENCES cashiers(id)
)

# Mobile (Firebase/Firestore):
# Collection: "shifts"
# Document structure:
{
    "cashier_id": "string (reference to cashiers collection)",
    "cashier_name": "string (denormalized for queries)",
    "shift_type": "string ('morning' or 'night')",
    "date": "string (YYYY-MM-DD format)",
    "start_time": "string (ISO format)",
    "end_time": "string (ISO format, null if active)",
    "status": "string ('active' or 'completed')",
    "total_sales": "number (default: 0)",
    "total_revenue": "number (default: 0)",
    "created_at": "timestamp (server timestamp)",
    "updated_at": "timestamp"
}

### 3. EXISTING TABLE: receipts - ADD COLUMNS
# Desktop (SQLite):
ALTER TABLE receipts ADD COLUMN cashier_id INTEGER
ALTER TABLE receipts ADD COLUMN shift_id INTEGER
ALTER TABLE receipts ADD COLUMN shift_type TEXT

# Mobile (Firebase/Firestore):
# Collection: "receipts"
# Add these fields to existing documents:
{
    "cashier_id": "string (reference to cashiers collection)",
    "cashier_name": "string (denormalized)",
    "shift_id": "string (reference to shifts collection)",
    "shift_type": "string ('morning' or 'night')"
}

### 4. NEW TABLE: shift_handover (for shift handover notes)
# Desktop (SQLite):
CREATE TABLE IF NOT EXISTS shift_handover (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_shift_id INTEGER NOT NULL,
    to_shift_id INTEGER NOT NULL,
    notes TEXT,
    cash_handover REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(from_shift_id) REFERENCES shifts(id),
    FOREIGN KEY(to_shift_id) REFERENCES shifts(id)
)

# Mobile (Firebase/Firestore):
# Collection: "shift_handover"
# Document structure:
{
    "from_shift_id": "string (reference to shifts)",
    "to_shift_id": "string (reference to shifts)",
    "from_cashier_name": "string",
    "to_cashier_name": "string",
    "notes": "string",
    "cash_handover": "number",
    "created_at": "timestamp (server timestamp)"
}

## ============================================
# INDEXES FOR PERFORMANCE
## ============================================

# Desktop (SQLite):
CREATE INDEX IF NOT EXISTS idx_shifts_cashier ON shifts(cashier_id);
CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(date);
CREATE INDEX IF NOT EXISTS idx_shifts_type ON shifts(shift_type);
CREATE INDEX IF NOT EXISTS idx_receipts_cashier ON receipts(cashier_id);
CREATE INDEX IF NOT EXISTS idx_receipts_shift ON receipts(shift_id);
CREATE INDEX IF NOT EXISTS idx_receipts_shift_type ON receipts(shift_type);

# Mobile (Firebase/Firestore):
# Create composite indexes:
# shifts collection: [cashier_id, date], [date, shift_type]
# receipts collection: [cashier_id], [shift_id], [shift_type, date]

## ============================================
# FIREBASE SYNC CHANGES
## ============================================

### 1. SYNC QUEUE TABLE ADDITION
# Desktop (SQLite):
# The sync_queue table already exists, just ensure it can handle new tables
# No changes needed - it's generic (table_name, record_id, action)

### 2. SYNC FUNCTIONS TO ADD

# Desktop - Add to firebase_sync.py:

def sync_cashier_to_firebase(cashier_id):
    """Sync a single cashier to Firebase"""
    cur.execute("SELECT * FROM cashiers WHERE id=?", (cashier_id,))
    cashier = cur.fetchone()
    if not cashier:
        return
    
    doc_ref = db.collection('cashiers').document(str(cashier_id))
    doc_ref.set({
        'name': cashier[1],
        'active': bool(cashier[2]),
        'created_at': cashier[3],
        'updated_at': datetime.now().isoformat()
    }, merge=True)
    
    # Mark as synced
    cur.execute("DELETE FROM sync_queue WHERE table_name='cashiers' AND record_id=?", (cashier_id,))
    conn.commit()

def sync_shift_to_firebase(shift_id):
    """Sync a single shift to Firebase"""
    cur.execute("""
        SELECT s.*, c.name as cashier_name 
        FROM shifts s 
        JOIN cashiers c ON s.cashier_id = c.id 
        WHERE s.id=?
    """, (shift_id,))
    shift = cur.fetchone()
    if not shift:
        return
    
    doc_ref = db.collection('shifts').document(str(shift_id))
    doc_ref.set({
        'cashier_id': str(shift[1]),
        'cashier_name': shift[11],  # cashier_name from join
        'shift_type': shift[2],
        'date': shift[3],
        'start_time': shift[4],
        'end_time': shift[5],
        'status': shift[6],
        'total_sales': shift[7] or 0,
        'total_revenue': shift[8] or 0,
        'created_at': shift[9],
        'updated_at': shift[10]
    }, merge=True)
    
    # Mark as synced
    cur.execute("DELETE FROM sync_queue WHERE table_name='shifts' AND record_id=?", (shift_id,))
    conn.commit()

def sync_shift_handover_to_firebase(handover_id):
    """Sync shift handover to Firebase"""
    cur.execute("""
        SELECT sh.*, 
               c1.name as from_cashier_name, 
               c2.name as to_cashier_name
        FROM shift_handover sh
        JOIN shifts s1 ON sh.from_shift_id = s1.id
        JOIN shifts s2 ON sh.to_shift_id = s2.id
        JOIN cashiers c1 ON s1.cashier_id = c1.id
        JOIN cashiers c2 ON s2.cashier_id = c2.id
        WHERE sh.id=?
    """, (handover_id,))
    handover = cur.fetchone()
    if not handover:
        return
    
    doc_ref = db.collection('shift_handover').document(str(handover_id))
    doc_ref.set({
        'from_shift_id': str(handover[1]),
        'to_shift_id': str(handover[2]),
        'from_cashier_name': handover[7],
        'to_cashier_name': handover[8],
        'notes': handover[3],
        'cash_handover': handover[4] or 0,
        'created_at': handover[5]
    }, merge=True)
    
    # Mark as synced
    cur.execute("DELETE FROM sync_queue WHERE table_name='shift_handover' AND record_id=?", (handover_id,))
    conn.commit()

def sync_receipt_with_shift(receipt_id):
    """Sync receipt with new shift fields"""
    cur.execute("SELECT * FROM receipts WHERE id=?", (receipt_id,))
    receipt = cur.fetchone()
    if not receipt:
        return
    
    # Get column names dynamically
    cur.execute("PRAGMA table_info(receipts)")
    columns = [col[1] for col in cur.fetchall()]
    
    receipt_data = {
        'total': receipt[1] if len(receipt) > 1 else 0,
        'profit': receipt[2] if len(receipt) > 2 else 0,
        'date': receipt[3] if len(receipt) > 3 else datetime.now().isoformat(),
    }
    
    # Add new fields if they exist
    if 'cashier_id' in columns and len(receipt) > 8:
        receipt_data['cashier_id'] = str(receipt[8]) if receipt[8] else None
    if 'shift_id' in columns and len(receipt) > 9:
        receipt_data['shift_id'] = str(receipt[9]) if receipt[9] else None
    if 'shift_type' in columns and len(receipt) > 10:
        receipt_data['shift_type'] = receipt[10]
    if 'status' in columns:
        status_idx = columns.index('status')
        receipt_data['status'] = receipt[status_idx]
    if 'customer' in columns:
        customer_idx = columns.index('customer')
        receipt_data['customer'] = receipt[customer_idx]
    
    # Get cashier name if cashier_id exists
    if receipt_data.get('cashier_id'):
        cur.execute("SELECT name FROM cashiers WHERE id=?", (receipt[8],))
        cashier = cur.fetchone()
        if cashier:
            receipt_data['cashier_name'] = cashier[0]
    
    doc_ref = db.collection('receipts').document(str(receipt_id))
    doc_ref.set(receipt_data, merge=True)
    
    # Mark as synced
    cur.execute("DELETE FROM sync_queue WHERE table_name='receipts' AND record_id=?", (receipt_id,))
    conn.commit()

# Mobile - Firebase Realtime Listeners:
// Add these listeners to your mobile app

// Listen for cashiers changes
firebase.firestore().collection('cashiers')
    .onSnapshot((snapshot) => {
        snapshot.docChanges().forEach((change) => {
            if (change.type === "added") {
                // Add to local SQLite/Room database
                localDB.insertCashier(change.doc.data(), change.doc.id);
            } else if (change.type === "modified") {
                // Update local database
                localDB.updateCashier(change.doc.data(), change.doc.id);
            } else if (change.type === "removed") {
                // Delete from local database
                localDB.deleteCashier(change.doc.id);
            }
        });
    });

// Listen for shifts changes
firebase.firestore().collection('shifts')
    .where('date', '>=', getTodayDate())
    .onSnapshot((snapshot) => {
        snapshot.docChanges().forEach((change) => {
            if (change.type === "added") {
                localDB.insertShift(change.doc.data(), change.doc.id);
            } else if (change.type === "modified") {
                localDB.updateShift(change.doc.data(), change.doc.id);
            } else if (change.type === "removed") {
                localDB.deleteShift(change.doc.id);
            }
        });
    });

// Listen for receipts with shift data
firebase.firestore().collection('receipts')
    .orderBy('date', 'desc')
    .limit(50)
    .onSnapshot((snapshot) => {
        snapshot.docChanges().forEach((change) => {
            // Handle receipt changes with shift information
            if (change.type === "added" || change.type === "modified") {
                localDB.upsertReceipt(change.doc.data(), change.doc.id);
            }
        });
    });

## ============================================
# DATA MIGRATION SCRIPT
## ============================================

# Desktop - Run this once to migrate existing data:

def migrate_existing_data():
    """Migrate existing receipts to have shift data"""
    
    # 1. Add columns if they don't exist
    cur.execute("PRAGMA table_info(receipts)")
    cols = [c[1] for c in cur.fetchall()]
    
    if 'cashier_id' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN cashier_id INTEGER")
    if 'shift_id' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN shift_id INTEGER")
    if 'shift_type' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN shift_type TEXT")
    
    # 2. Create default cashier if none exists
    cur.execute("SELECT COUNT(*) FROM cashiers")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO cashiers (name, active) VALUES ('Default Cashier', 1)")
        default_cashier_id = cur.lastrowid
    else:
        cur.execute("SELECT id FROM cashiers LIMIT 1")
        default_cashier_id = cur.fetchone()[0]
    
    # 3. For existing receipts, determine shift based on time
    cur.execute("SELECT id, date FROM receipts WHERE cashier_id IS NULL")
    existing_receipts = cur.fetchall()
    
    for receipt_id, receipt_date in existing_receipts:
        try:
            dt = datetime.fromisoformat(receipt_date)
            hour = dt.hour
            
            # Morning shift: 6AM - 2PM (6-14)
            # Night shift: 2PM - 10PM (14-22)
            if 6 <= hour < 14:
                shift_type = 'morning'
            elif 14 <= hour < 22:
                shift_type = 'night'
            else:
                shift_type = 'night'  # Default to night for late hours
            
            # Find or create shift for this date and type
            date_str = dt.date().isoformat()
            cur.execute("""
                SELECT id FROM shifts 
                WHERE date = ? AND shift_type = ? 
                ORDER BY id DESC LIMIT 1
            """, (date_str, shift_type))
            shift = cur.fetchone()
            
            if not shift:
                # Create new shift
                cur.execute("""
                    INSERT INTO shifts (cashier_id, shift_type, date, start_time, status)
                    VALUES (?, ?, ?, ?, 'completed')
                """, (default_cashier_id, shift_type, date_str, receipt_date))
                shift_id = cur.lastrowid
            else:
                shift_id = shift[0]
            
            # Update receipt
            cur.execute("""
                UPDATE receipts 
                SET cashier_id = ?, shift_id = ?, shift_type = ?
                WHERE id = ?
            """, (default_cashier_id, shift_id, shift_type, receipt_id))
            
        except Exception as e:
            print(f"Error migrating receipt {receipt_id}: {e}")
    
    conn.commit()
    print("Migration completed!")

# Mobile - Equivalent migration:
// Run this on app startup if migration not done

async function migrateExistingReceipts() {
    const migrationFlag = await AsyncStorage.getItem('shift_migration_done');
    if (migrationFlag === 'true') return;
    
    const receipts = await localDB.getReceiptsWithoutShift();
    const defaultCashier = await localDB.getOrCreateDefaultCashier();
    
    for (const receipt of receipts) {
        const date = new Date(receipt.date);
        const hour = date.getHours();
        const shiftType = (hour >= 6 && hour < 14) ? 'morning' : 'night';
        const dateStr = date.toISOString().split('T')[0];
        
        let shift = await localDB.getShiftByDateAndType(dateStr, shiftType);
        if (!shift) {
            shift = await localDB.createShift({
                cashier_id: defaultCashier.id,
                shift_type: shiftType,
                date: dateStr,
                start_time: receipt.date,
                status: 'completed'
            });
        }
        
        await localDB.updateReceiptShift(receipt.id, {
            cashier_id: defaultCashier.id,
            shift_id: shift.id,
            shift_type: shiftType
        });
    }
    
    await AsyncStorage.setItem('shift_migration_done', 'true');
}

## ============================================
# STATE MANAGEMENT CHANGES
## ============================================

# Desktop - Update state.py:
cart = {}
current_cashier = {}  # Add this
current_shift = {}   # Add this

# Mobile - Add to your state management (Redux/ContextProvider):
const initialState = {
    cart: [],
    currentCashier: null,
    currentShift: null,
    // ... other existing state
};

## ============================================
# API ENDPOINTS (if you have a backend)
## ============================================

# Add these endpoints to your backend API:

# GET /api/cashiers - List all cashiers
# POST /api/cashiers - Create new cashier
# PUT /api/cashiers/:id - Update cashier
# DELETE /api/cashiers/:id - Delete cashier

# GET /api/shifts - List shifts with filters
# POST /api/shifts - Start new shift
# PUT /api/shifts/:id/end - End shift
# GET /api/shifts/:id/handover - Get handover info

# GET /api/receipts?shift_id=:id - Get receipts by shift
# GET /api/analytics/shifts/:id - Get shift analytics

## ============================================
# TESTING CHECKLIST
## ============================================

After implementing these changes, test:

[ ] Cashier creation and listing
[ ] Shift starting and ending
[ ] Receipt creation with shift assignment
[ ] Shift handover process
[ ] Analytics by shift
[ ] Firebase sync for new tables
[ ] Mobile app sync with desktop
[ ] Data migration for existing receipts
[ ] Performance with indexes
[ ] Offline mode (if applicable)

## ============================================
# ROLLBACK PLAN
## ============================================

If you need to rollback:

# Desktop:
# 1. Drop new tables: DROP TABLE shift_handover; DROP TABLE shifts; DROP TABLE cashiers;
# 2. Remove columns: 
#    ALTER TABLE receipts DROP COLUMN cashier_id;
#    ALTER TABLE receipts DROP COLUMN shift_id;
#    ALTER TABLE receipts DROP COLUMN shift_type;
# 3. Remove indexes

# Mobile:
# 1. Delete collections from Firebase
# 2. Remove local database tables/columns
# 3. Revert state management changes

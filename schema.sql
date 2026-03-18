-- ============================================
-- Supabase SQL Schema for Invoice Software
-- DROP old tables first if migrating (uncomment):
--   DROP TABLE IF EXISTS approved_invoice_items, approved_invoices,
--     invoice_items, invoices, warehouse_stock, warehouses, addas, items, parties CASCADE;
-- Copy-paste this into the Supabase SQL Editor
-- ============================================

-- If tables already exist, run these migration statements once instead:
-- ALTER TABLE items ADD COLUMN IF NOT EXISTS discount NUMERIC(8,2) NOT NULL DEFAULT 0;
-- ALTER TABLE invoice_items ADD COLUMN IF NOT EXISTS discount NUMERIC(8,2) NOT NULL DEFAULT 0;
-- ALTER TABLE approved_invoice_items ADD COLUMN IF NOT EXISTS discount NUMERIC(8,2) NOT NULL DEFAULT 0;
-- ALTER TABLE addas ADD COLUMN IF NOT EXISTS number TEXT NOT NULL DEFAULT '';

-- 1. Parties table
CREATE TABLE parties (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- 2. Items table (item_code + name + box_qty + default discount %)
CREATE TABLE items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    box_qty INTEGER NOT NULL DEFAULT 1,
    discount NUMERIC(8,2) NOT NULL DEFAULT 0
);

-- 3. Addas table (delivery adda names)
CREATE TABLE addas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    number TEXT NOT NULL DEFAULT '',
    UNIQUE(name, number)
);

-- 4. Warehouses (3 fixed warehouses)
CREATE TABLE warehouses (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- 5. Warehouse stock per item per warehouse
CREATE TABLE warehouse_stock (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_id BIGINT NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    stock INTEGER NOT NULL DEFAULT 0,
    UNIQUE(warehouse_id, item_id)
);

-- 6. Invoices (header - pending, awaiting admin approval)
CREATE TABLE invoices (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_number TEXT NOT NULL UNIQUE,
    party_id BIGINT NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    adda_id BIGINT NOT NULL REFERENCES addas(id) ON DELETE CASCADE,
    delivery_paid BOOLEAN NOT NULL DEFAULT false,
    delivery_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Invoice line items (multiple items per invoice)
CREATE TABLE invoice_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    discount NUMERIC(8,2) NOT NULL DEFAULT 0
);

-- 8. Approved invoices (header copy after admin approves)
CREATE TABLE approved_invoices (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    invoice_number TEXT NOT NULL,
    party_id BIGINT NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    adda_id BIGINT NOT NULL REFERENCES addas(id) ON DELETE CASCADE,
    warehouse_id BIGINT REFERENCES warehouses(id) ON DELETE SET NULL,
    delivery_paid BOOLEAN NOT NULL DEFAULT false,
    delivery_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    invoice_date DATE NOT NULL,
    approved_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Approved invoice line items
CREATE TABLE approved_invoice_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    approved_invoice_id BIGINT NOT NULL REFERENCES approved_invoices(id) ON DELETE CASCADE,
    item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    discount NUMERIC(8,2) NOT NULL DEFAULT 0
);

-- Indexes
CREATE INDEX idx_items_code ON items(item_code);
CREATE INDEX idx_items_name ON items(name);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_party ON invoices(party_id);
CREATE INDEX idx_invoices_created ON invoices(created_at DESC);
CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX idx_approved_invoices_party ON approved_invoices(party_id);
CREATE INDEX idx_approved_invoice_items_inv ON approved_invoice_items(approved_invoice_id);
CREATE INDEX idx_warehouse_stock_wh ON warehouse_stock(warehouse_id);
CREATE INDEX idx_warehouse_stock_item ON warehouse_stock(item_id);

-- Enable Row Level Security (RLS)
ALTER TABLE parties ENABLE ROW LEVEL SECURITY;
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE addas ENABLE ROW LEVEL SECURITY;
ALTER TABLE warehouses ENABLE ROW LEVEL SECURITY;
ALTER TABLE warehouse_stock ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE approved_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE approved_invoice_items ENABLE ROW LEVEL SECURITY;

-- Open policies (tighten later when adding auth)
CREATE POLICY "Allow all on parties" ON parties FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on items" ON items FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on addas" ON addas FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on warehouses" ON warehouses FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on warehouse_stock" ON warehouse_stock FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on invoices" ON invoices FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on invoice_items" ON invoice_items FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on approved_invoices" ON approved_invoices FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on approved_invoice_items" ON approved_invoice_items FOR ALL USING (true) WITH CHECK (true);

-- Seed 3 warehouses
INSERT INTO warehouses (name) VALUES ('Warehouse 1'), ('Warehouse 2'), ('Warehouse 3');

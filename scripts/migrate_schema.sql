-- Afrimail Database Schema Migration
-- This script creates all necessary tables for the Afrimail application
-- Run this on your PostgreSQL database before starting the backend

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Core User Tables
-- ============================================

-- Users extended table
CREATE TABLE IF NOT EXISTS users_extended (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth DATE,
    gender TEXT CHECK (gender IN ('male', 'female', 'non-binary', 'prefer-not-to-say', NULL)),
    recovery_email TEXT,
    recovery_phone TEXT,
    password_hash TEXT,
    is_suspended BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_extended_email ON users_extended(email);
CREATE INDEX IF NOT EXISTS idx_users_extended_created_at ON users_extended(created_at);

-- ============================================
-- Admin Tables
-- ============================================

-- Admin roles
CREATE TABLE IF NOT EXISTS admin_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '{}',
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin users
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role_id UUID REFERENCES admin_roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);

-- ============================================
-- Mailbox & Storage Tables
-- ============================================

-- Mailbox metadata
CREATE TABLE IF NOT EXISTS mailbox_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    user_id UUID REFERENCES users_extended(id) ON DELETE CASCADE,
    quota_bytes BIGINT DEFAULT 0,
    usage_bytes BIGINT DEFAULT 0,
    last_synced TIMESTAMPTZ DEFAULT NOW(),
    last_sync TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mailbox_metadata_email ON mailbox_metadata(email);
CREATE INDEX IF NOT EXISTS idx_mailbox_metadata_user_id ON mailbox_metadata(user_id);

-- ============================================
-- Audit & Activity Tables
-- ============================================

-- Audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type TEXT NOT NULL,
    admin_email TEXT NOT NULL,
    target_user_email TEXT,
    details JSONB,
    ip_address TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_admin_email ON audit_logs(admin_email);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action_type ON audit_logs(action_type);

-- Login activity
CREATE TABLE IF NOT EXISTS login_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_email TEXT NOT NULL,
    login_time TIMESTAMPTZ DEFAULT NOW(),
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    failure_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_login_activity_user_email ON login_activity(user_email);
CREATE INDEX IF NOT EXISTS idx_login_activity_login_time ON login_activity(login_time DESC);
CREATE INDEX IF NOT EXISTS idx_login_activity_success ON login_activity(success);

-- ============================================
-- Support & Announcements Tables
-- ============================================

-- Support tickets
CREATE TABLE IF NOT EXISTS support_tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_type TEXT NOT NULL CHECK (ticket_type IN ('password_reset', 'account_unlock', 'quota_increase', 'general')),
    user_email TEXT NOT NULL,
    user_id UUID REFERENCES users_extended(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'resolved', 'rejected')),
    priority TEXT DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    subject TEXT,
    message TEXT,
    description TEXT,
    resolution_notes TEXT,
    assigned_to TEXT,
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_user_email ON support_tickets(user_email);
CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets(created_at DESC);

-- Announcements
CREATE TABLE IF NOT EXISTS announcements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    target_group TEXT DEFAULT 'all',
    priority TEXT DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_announcements_published ON announcements(published);
CREATE INDEX IF NOT EXISTS idx_announcements_created_at ON announcements(created_at DESC);

-- ============================================
-- Email Alias Tables
-- ============================================

-- Email aliases
CREATE TABLE IF NOT EXISTS email_aliases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alias_address TEXT UNIQUE NOT NULL,
    target_addresses TEXT[] NOT NULL,
    is_distribution_list BOOLEAN DEFAULT FALSE,
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_by TEXT,
    mailcow_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_aliases_alias_address ON email_aliases(alias_address);
CREATE INDEX IF NOT EXISTS idx_email_aliases_active ON email_aliases(active);
CREATE INDEX IF NOT EXISTS idx_email_aliases_mailcow_id ON email_aliases(mailcow_id);

-- ============================================
-- Domain Tables
-- ============================================

-- Mail domains
CREATE TABLE IF NOT EXISTS mail_domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain TEXT UNIQUE NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mail_domains_domain ON mail_domains(domain);

-- Custom domains
CREATE TABLE IF NOT EXISTS custom_domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain TEXT UNIQUE NOT NULL,
    user_id UUID REFERENCES users_extended(id) ON DELETE CASCADE,
    verification_status TEXT DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'failed')),
    verification_code TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_custom_domains_user_id ON custom_domains(user_id);

-- ============================================
-- Group Tables
-- ============================================

-- User groups
CREATE TABLE IF NOT EXISTS user_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    color TEXT DEFAULT 'blue',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User group members
CREATE TABLE IF NOT EXISTS user_group_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users_extended(id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES user_groups(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    added_by UUID REFERENCES admin_users(id),
    UNIQUE(user_id, group_id)
);

CREATE INDEX IF NOT EXISTS idx_user_group_members_user_id ON user_group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_user_group_members_group_id ON user_group_members(group_id);

-- ============================================
-- Template Tables
-- ============================================

-- User templates
CREATE TABLE IF NOT EXISTS user_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    quota_bytes BIGINT DEFAULT 5368709120,
    permissions JSONB DEFAULT '{}',
    is_system_template BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Scheduled Actions Tables
-- ============================================

-- Scheduled actions
CREATE TABLE IF NOT EXISTS scheduled_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_ids JSONB DEFAULT '[]',
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'pending',
    action_data JSONB DEFAULT '{}',
    created_by UUID REFERENCES admin_users(id),
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_actions_status ON scheduled_actions(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_actions_scheduled_for ON scheduled_actions(scheduled_for);

-- Bulk import logs
CREATE TABLE IF NOT EXISTS bulk_import_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename TEXT NOT NULL,
    total_rows INTEGER DEFAULT 0,
    successful_imports INTEGER DEFAULT 0,
    failed_imports INTEGER DEFAULT 0,
    error_details JSONB DEFAULT '[]',
    imported_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Sending Limits Tables
-- ============================================

-- Sending tiers
CREATE TABLE IF NOT EXISTS sending_tiers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    daily_limit INTEGER NOT NULL,
    hourly_limit INTEGER NOT NULL,
    price_monthly NUMERIC(10, 2) DEFAULT 0,
    features JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Email sending limits
CREATE TABLE IF NOT EXISTS email_sending_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE,
    tier_id UUID REFERENCES sending_tiers(id),
    tier_name TEXT DEFAULT 'free',
    daily_limit INTEGER DEFAULT 50,
    hourly_limit INTEGER DEFAULT 10,
    emails_sent_today INTEGER DEFAULT 0,
    emails_sent_this_hour INTEGER DEFAULT 0,
    last_reset_date DATE DEFAULT CURRENT_DATE,
    last_reset_hour TIMESTAMPTZ DEFAULT NOW(),
    is_sending_enabled BOOLEAN DEFAULT TRUE,
    custom_limit_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_sending_limits_user_id ON email_sending_limits(user_id);
CREATE INDEX IF NOT EXISTS idx_email_sending_limits_tier ON email_sending_limits(tier_name);

-- Email send logs
CREATE TABLE IF NOT EXISTS email_send_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    recipient_email TEXT NOT NULL,
    recipient_count INTEGER DEFAULT 1,
    subject TEXT,
    status TEXT DEFAULT 'sent',
    failure_reason TEXT,
    blocked_reason TEXT,
    ip_address INET,
    user_agent TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_send_logs_user_id ON email_send_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_email_send_logs_sent_at ON email_send_logs(sent_at DESC);

-- Sending limit violations
CREATE TABLE IF NOT EXISTS sending_limit_violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    violation_type TEXT NOT NULL,
    attempted_count INTEGER NOT NULL,
    limit_at_time INTEGER NOT NULL,
    violation_details JSONB DEFAULT '{}',
    action_taken TEXT DEFAULT 'logged',
    admin_notes TEXT,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_violations_user_id ON sending_limit_violations(user_id);
CREATE INDEX IF NOT EXISTS idx_violations_created ON sending_limit_violations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_violations_unresolved ON sending_limit_violations(is_resolved) WHERE is_resolved = FALSE;

-- ============================================
-- Signup & Password Reset Tables
-- ============================================

-- Signup attempts
CREATE TABLE IF NOT EXISTS signup_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip_address TEXT NOT NULL,
    email_attempted TEXT NOT NULL,
    hcaptcha_verified BOOLEAN DEFAULT FALSE,
    honeypot_filled BOOLEAN DEFAULT FALSE,
    success BOOLEAN DEFAULT FALSE,
    failure_reason TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signup_attempts_ip_address ON signup_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_signup_attempts_created_at ON signup_attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_signup_attempts_ip_created ON signup_attempts(ip_address, created_at);

-- Password resets
CREATE TABLE IF NOT EXISTS password_resets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    otp_type TEXT NOT NULL CHECK (otp_type IN ('email', 'sms')),
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_resets_email ON password_resets(email);
CREATE INDEX IF NOT EXISTS idx_password_resets_expires_at ON password_resets(expires_at);

-- ============================================
-- System Settings Table
-- ============================================

-- System settings
CREATE TABLE IF NOT EXISTS system_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    setting_key TEXT UNIQUE NOT NULL,
    setting_value JSONB NOT NULL,
    description TEXT,
    updated_by TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Activity Logs Table
-- ============================================

-- Activity logs
CREATE TABLE IF NOT EXISTS activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users_extended(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    description TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at DESC);

-- ============================================
-- Default Data
-- ============================================

-- Insert default admin roles
INSERT INTO admin_roles (name, description, permissions, is_system_role) VALUES
    ('Super Admin', 'Full system access with all permissions',
     '{"users": {"view": true, "create": true, "edit": true, "delete": true, "suspend": true}, "admins": {"view": true, "create": true, "edit": true, "delete": true}}',
     TRUE),
    ('User Manager', 'Manage user accounts and mailboxes',
     '{"users": {"view": true, "create": true, "edit": true, "delete": false, "suspend": true}}',
     TRUE),
    ('Support Manager', 'Handle support tickets and announcements',
     '{"users": {"view": true}, "support": {"view": true, "edit": true}}',
     TRUE)
ON CONFLICT (name) DO NOTHING;

-- Insert default sending tiers
INSERT INTO sending_tiers (name, display_name, daily_limit, hourly_limit, price_monthly, features, sort_order) VALUES
    ('free', 'Free', 50, 10, 0, '["Basic email sending", "Standard support"]', 1),
    ('basic', 'Basic', 500, 50, 9.99, '["Increased sending limits", "Priority support"]', 2),
    ('premium', 'Premium', 2000, 200, 29.99, '["High volume sending", "Premium support", "API access"]', 3),
    ('enterprise', 'Enterprise', 999999, 99999, 99.99, '["Unlimited sending", "Dedicated support", "SLA guarantee"]', 4)
ON CONFLICT (name) DO NOTHING;

-- Insert default mail domain
INSERT INTO mail_domains (domain, is_primary, is_active, description) VALUES
    ('afrimail.com', TRUE, TRUE, 'Primary mail domain for Afrimail service')
ON CONFLICT (domain) DO NOTHING;

-- Insert default system settings
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
    ('quota_presets', '{"presets": [{"name": "Basic", "value": 1073741824}, {"name": "Standard", "value": 5368709120}, {"name": "Premium", "value": 10737418240}]}', 'Default quota presets'),
    ('maintenance_mode', '{"enabled": false, "message": "System maintenance in progress."}', 'Maintenance mode configuration'),
    ('default_user_quota', '{"value": 5368709120}', 'Default quota for new users (5GB)')
ON CONFLICT (setting_key) DO NOTHING;

-- Insert default user templates
INSERT INTO user_templates (name, description, quota_bytes, permissions, is_system_template) VALUES
    ('Basic User', 'Entry-level account with 1GB storage', 1073741824, '{"email": true, "calendar": false}', TRUE),
    ('Standard User', 'Standard account with 5GB storage', 5368709120, '{"email": true, "calendar": true}', TRUE),
    ('Premium User', 'Premium account with 15GB storage', 16106127360, '{"email": true, "calendar": true, "priority_support": true}', TRUE)
ON CONFLICT (name) DO NOTHING;

-- Insert default user groups
INSERT INTO user_groups (name, description, color) VALUES
    ('General', 'General user group', 'gray'),
    ('Priority', 'Priority users requiring special attention', 'yellow'),
    ('Enterprise', 'Enterprise customers', 'blue'),
    ('Beta Testers', 'Users testing new features', 'purple')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- Create update timestamp trigger function
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with updated_at
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['users_extended', 'email_aliases', 'support_tickets', 'mail_domains',
                                  'user_groups', 'user_templates', 'email_sending_limits', 'sending_tiers'])
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%s_updated_at ON %s;
            CREATE TRIGGER update_%s_updated_at
                BEFORE UPDATE ON %s
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        ', t, t, t, t);
    END LOOP;
END $$;

-- Done!
SELECT 'Database schema migration complete!' AS status;

-- QuantLab Knowledge Lake Schema with RBAC
-- PostgreSQL schema for multi-user RBAC

-- ============================================================
-- Users & Roles
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE user_role AS ENUM ('admin', 'researcher', 'viewer', 'operator');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role user_role NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ============================================================
-- Teams / Organizations
-- ============================================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, user_id)
);

-- ============================================================
-- Campaigns (with ownership)
-- ============================================================

CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    config JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_campaigns_owner ON campaigns(owner_id);
CREATE INDEX idx_campaigns_org ON campaigns(organization_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);

-- Campaign shares (for collaboration)
CREATE TABLE campaign_shares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    permission TEXT NOT NULL DEFAULT 'read', -- 'read', 'write', 'admin'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    UNIQUE (campaign_id, user_id, organization_id)
);

-- ============================================================
-- Pipeline Runs (with ownership)
-- ============================================================

CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id TEXT UNIQUE NOT NULL,
    pipeline_name TEXT NOT NULL,
    pipeline_config JSONB NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    status TEXT NOT NULL DEFAULT 'pending',
    status_detail JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds REAL,
    error_message TEXT,
    config_snapshot JSONB NOT NULL,
    artifacts JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_runs_owner ON pipeline_runs(owner_id);
CREATE INDEX idx_pipeline_runs_org ON pipeline_runs(organization_id);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_runs_created ON pipeline_runs(created_at DESC);

-- Stage runs within pipeline
CREATE TABLE stage_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    stage_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds REAL,
    error_message TEXT,
    input_artifacts JSONB DEFAULT '{}',
    output_artifacts JSONB DEFAULT '{}',
    config_snapshot JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stage_runs_pipeline ON stage_runs(pipeline_run_id);
CREATE INDEX idx_stage_runs_status ON stage_runs(status);

-- ============================================================
-- Knowledge Lake Index (enhanced for RBAC)
-- ============================================================

CREATE TABLE knowledge_index (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    modified_at TIMESTAMPTZ NOT NULL,
    directory TEXT NOT NULL,
    campaign_id UUID REFERENCES campaigns(id),
    pipeline_run_id UUID REFERENCES pipeline_runs(id),
    owner_id UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    tags TEXT[] DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    linked_campaigns UUID[] DEFAULT '{}',
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id)
);

CREATE INDEX idx_knowledge_campaign ON knowledge_index(campaign_id);
CREATE INDEX idx_knowledge_pipeline ON knowledge_index(pipeline_run_id);
CREATE INDEX idx_knowledge_owner ON knowledge_index(owner_id);
CREATE INDEX idx_knowledge_org ON knowledge_index(organization_id);
CREATE INDEX idx_knowledge_tags ON knowledge_index USING GIN(tags);
CREATE INDEX idx_knowledge_metrics ON knowledge_index USING GIN(metrics);
CREATE INDEX idx_knowledge_path ON knowledge_index(path);

-- ============================================================
-- Campaign Metrics (for reporting)
-- ============================================================

CREATE TABLE campaign_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    metric_unit TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pipeline_run_id UUID REFERENCES pipeline_runs(id)
);

CREATE INDEX idx_metrics_campaign ON campaign_metrics(campaign_id);
CREATE INDEX idx_metrics_name ON campaign_metrics(metric_name);
CREATE INDEX idx_metrics_recorded ON campaign_metrics(recorded_at DESC);

-- ============================================================
-- API Keys (for programmatic access)
-- ============================================================

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    scopes TEXT[] DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- ============================================================
-- Audit Log
-- ============================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    old_data JSONB,
    new_data JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_org ON audit_logs(organization_id);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- ============================================================
-- Triggers for updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaigns_updated_at BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pipeline_runs_updated_at BEFORE UPDATE ON pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Row Level Security (RLS) Policies
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_metrics ENABLE ROW LEVEL SECURITY;

-- Policies: Users can access their own campaigns
CREATE POLICY campaigns_owner_access ON campaigns
    FOR ALL USING (owner_id = current_user_id());

CREATE POLICY campaigns_org_access ON campaigns
    FOR ALL USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = current_user_id()
        )
    );

-- Pipeline runs
CREATE POLICY pipeline_runs_owner_access ON pipeline_runs
    FOR ALL USING (owner_id = current_user_id());

CREATE POLICY pipeline_runs_org_access ON pipeline_runs
    FOR ALL USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = current_user_id()
        )
    );

-- Knowledge index
CREATE POLICY knowledge_index_owner_access ON knowledge_index
    FOR ALL USING (owner_id = current_user_id());

CREATE POLICY knowledge_index_org_access ON knowledge_index
    FOR ALL USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = current_user_id()
        )
    );

-- Public read for public campaigns
CREATE POLICY campaigns_public_read ON campaigns
    FOR SELECT USING (is_public = TRUE);

-- Helper function for current user
CREATE OR REPLACE FUNCTION current_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN COALESCE(
        current_setting('app.current_user_id', true)::UUID,
        (SELECT id FROM users WHERE email = current_user)::UUID
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
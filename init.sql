-- Database initialization script (PostgreSQL)

\set ON_ERROR_STOP on

\if :{?HOSPITOLL_ADMIN_PASSWORD}
\else
\echo 'ERROR: HOSPITOLL_ADMIN_PASSWORD is required. Example: psql -v HOSPITOLL_ADMIN_PASSWORD=... -v HOSPITOLL_APP_PASSWORD=... -f init.sql'
\quit 1
\endif

\if :{?HOSPITOLL_APP_PASSWORD}
\else
\echo 'ERROR: HOSPITOLL_APP_PASSWORD is required. Example: psql -v HOSPITOLL_ADMIN_PASSWORD=... -v HOSPITOLL_APP_PASSWORD=... -f init.sql'
\quit 1
\endif

-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema
CREATE SCHEMA IF NOT EXISTS hospitoll;

-- Set search path
ALTER DATABASE hospitoll_db SET search_path TO hospitoll, public;

-- Create roles with proper permissions
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hospitoll_admin') THEN
		EXECUTE format('CREATE ROLE hospitoll_admin WITH LOGIN PASSWORD %L', :'HOSPITOLL_ADMIN_PASSWORD');
	ELSE
		EXECUTE format('ALTER ROLE hospitoll_admin WITH LOGIN PASSWORD %L', :'HOSPITOLL_ADMIN_PASSWORD');
	END IF;

	IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hospitoll_app') THEN
		EXECUTE format('CREATE ROLE hospitoll_app WITH LOGIN PASSWORD %L', :'HOSPITOLL_APP_PASSWORD');
	ELSE
		EXECUTE format('ALTER ROLE hospitoll_app WITH LOGIN PASSWORD %L', :'HOSPITOLL_APP_PASSWORD');
	END IF;
END
$$;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA hospitoll TO hospitoll_admin;
GRANT USAGE ON SCHEMA hospitoll TO hospitoll_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA hospitoll GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hospitoll_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA hospitoll GRANT USAGE, SELECT ON SEQUENCES TO hospitoll_app;

-- Create materialized views for analytics (if needed)
-- This will be created by Django migrations

-- Initialize Sparky database
-- This script runs automatically when the PostgreSQL container starts for the first time
-- It creates a separate database for Sparky so it doesn't share data with MetaMCP
--
-- The database name is controlled by the SPARKY_DB environment variable (default: sparky_db)

-- Create the sparky_db database if it doesn't exist
-- Note: We can't use environment variables directly in SQL files loaded by docker-entrypoint-initdb.d
-- The default name is sparky_db, but you can override it by setting SPARKY_DB in your .env file
-- If you need a custom database name, create the database manually or modify this file

SELECT 'CREATE DATABASE sparky_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sparky_db')\gexec

-- The database user (metamcp_user by default) already has access via the shared PostgreSQL instance
-- No additional grants needed since the user is already created by the main POSTGRES_DB

-- Connect to sparky_db and enable pgvector extension
\c sparky_db

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;


-- Migration 009: flag para forçar troca de senha no primeiro login
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false;

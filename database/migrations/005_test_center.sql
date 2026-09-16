CREATE TABLE test_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite VARCHAR(100) NOT NULL DEFAULT 'pytest',
    commit_sha VARCHAR(64),
    branch VARCHAR(255),
    environment VARCHAR(100) NOT NULL DEFAULT 'local',
    status VARCHAR(30) NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    passed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_test_runs_status ON test_runs(status);
CREATE INDEX ix_test_runs_created_at ON test_runs(created_at);

CREATE TABLE test_case_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
    node_id VARCHAR(500) NOT NULL,
    name VARCHAR(500) NOT NULL,
    file_path VARCHAR(500),
    class_name VARCHAR(255),
    status VARCHAR(30) NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_test_case_run_node UNIQUE (run_id, node_id)
);
CREATE INDEX ix_test_case_results_run_id ON test_case_results(run_id);
CREATE INDEX ix_test_case_results_status ON test_case_results(status);

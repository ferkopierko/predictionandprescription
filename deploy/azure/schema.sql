IF OBJECT_ID(N'dbo.hodnotenia', N'U') IS NULL
CREATE TABLE dbo.hodnotenia (
    id INT IDENTITY(1,1) PRIMARY KEY,
    vytvorene NVARCHAR(19) NOT NULL,
    zdroj NVARCHAR(40) NOT NULL,
    nazov NVARCHAR(200) NOT NULL DEFAULT N'',
    odvetvie NVARCHAR(200) NOT NULL,
    vzor_utoku NVARCHAR(200) NOT NULL,
    frekvencia FLOAT NOT NULL,
    p_nizky FLOAT NOT NULL,
    p_stredny FLOAT NOT NULL,
    p_vysoky FLOAT NOT NULL,
    predikovany_dopad NVARCHAR(40) NOT NULL,
    skutocny_dopad NVARCHAR(40),
    strata_incidentu FLOAT NOT NULL,
    ocakavana_strata FLOAT NOT NULL,
    opatrenie NVARCHAR(200) NOT NULL,
    opatrenia_cis NVARCHAR(MAX) NOT NULL,
    cena_opatrenia FLOAT NOT NULL,
    zostavajuca_strata FLOAT NOT NULL,
    cisty_prinos FLOAT NOT NULL,
    vstup NVARCHAR(MAX) NOT NULL
);

IF OBJECT_ID(N'dbo.company_profile', N'U') IS NULL
CREATE TABLE dbo.company_profile (
    id NVARCHAR(100) PRIMARY KEY, settings NVARCHAR(MAX) NOT NULL
);
IF OBJECT_ID(N'dbo.company_assets', N'U') IS NULL
CREATE TABLE dbo.company_assets (
    id NVARCHAR(100) PRIMARY KEY, name NVARCHAR(200) NOT NULL, category NVARCHAR(100) NOT NULL,
    quantity INT NOT NULL CHECK(quantity>0), address NVARCHAR(200) NOT NULL,
    technology NVARCHAR(200) NOT NULL, [owner] NVARCHAR(200) NOT NULL,
    criticality NVARCHAR(100) NOT NULL, model_asset NVARCHAR(200) NOT NULL, data_types NVARCHAR(MAX) NOT NULL
);
IF OBJECT_ID(N'dbo.company_findings', N'U') IS NULL
CREATE TABLE dbo.company_findings (
    id NVARCHAR(100) PRIMARY KEY, asset_id NVARCHAR(100) NOT NULL REFERENCES dbo.company_assets(id),
    title NVARCHAR(200) NOT NULL, severity NVARCHAR(100) NOT NULL, remediation NVARCHAR(MAX) NOT NULL,
    cost FLOAT NOT NULL CHECK(cost>=0), scenario NVARCHAR(100) NOT NULL, status NVARCHAR(100) NOT NULL,
    note NVARCHAR(MAX) NOT NULL DEFAULT N'', updated_at NVARCHAR(30) NOT NULL
);
IF OBJECT_ID(N'dbo.company_cases', N'U') IS NULL
CREATE TABLE dbo.company_cases (
    id INT IDENTITY(1,1) PRIMARY KEY, scenario NVARCHAR(100) NOT NULL,
    asset_id NVARCHAR(100) NOT NULL REFERENCES dbo.company_assets(id),
    finding_id NVARCHAR(100) REFERENCES dbo.company_findings(id), title NVARCHAR(200) NOT NULL,
    created_at NVARCHAR(30) NOT NULL, status NVARCHAR(100) NOT NULL DEFAULT N'Na vyhodnotenie',
    simulated INT NOT NULL DEFAULT 1
);
IF OBJECT_ID(N'dbo.company_assessments', N'U') IS NULL
CREATE TABLE dbo.company_assessments (
    assessment_id INT PRIMARY KEY REFERENCES dbo.hodnotenia(id) ON DELETE CASCADE,
    company_id NVARCHAR(100) NOT NULL, asset_id NVARCHAR(100) NOT NULL REFERENCES dbo.company_assets(id),
    finding_id NVARCHAR(100) REFERENCES dbo.company_findings(id),
    case_id INT REFERENCES dbo.company_cases(id), assumptions NVARCHAR(MAX) NOT NULL
);
IF OBJECT_ID(N'dbo.company_events', N'U') IS NULL
CREATE TABLE dbo.company_events (
    id INT IDENTITY(1,1) PRIMARY KEY, created_at NVARCHAR(30) NOT NULL,
    kind NVARCHAR(100) NOT NULL, detail NVARCHAR(MAX) NOT NULL
);

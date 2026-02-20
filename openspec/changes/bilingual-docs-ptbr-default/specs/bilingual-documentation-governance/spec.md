# bilingual-documentation-governance Specification

## ADDED Requirements

### Requirement: README SHALL Expose Portuguese Default With Explicit English Mirror

The repository SHALL publish Portuguese as the default landing language in
`README.md` and SHALL provide a mirrored English version in `README.en.md`.

#### Scenario: Reader opens repository home page

- **WHEN** a user opens the repository in GitHub
- **THEN** `README.md` MUST render in Portuguese
- **AND** the top section MUST provide a direct link to `README.en.md`

#### Scenario: Reader opens English README

- **WHEN** a user opens `README.en.md`
- **THEN** the file MUST provide a direct link back to `README.md`

### Requirement: Operational Docs SHALL Be Available In Both Languages

The operational documentation set under `docs/` SHALL be available in Portuguese
as primary content and SHALL include mirrored English files under `docs/en/`.

#### Scenario: Portuguese doc has English counterpart

- **WHEN** a Portuguese document exists in `docs/`
- **THEN** a file with equivalent scope MUST exist in `docs/en/`
- **AND** both files MUST expose PT/EN navigation links at the top

### Requirement: Documentation Changes SHALL Enforce Translation Synchronization

The contribution workflow SHALL require synchronization between Portuguese and
English documentation when either language is changed.

#### Scenario: Agent updates a documentation file

- **WHEN** `README.md` or any file under `docs/` is modified
- **THEN** the corresponding file in the other language MUST be updated in the
  same slice or pull request
- **AND** exceptions MUST be explicitly documented with follow-up action

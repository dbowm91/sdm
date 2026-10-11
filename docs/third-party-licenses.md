# Third-party license inventory and review status

[`third-party-license-inventory.json`](third-party-license-inventory.json) is
generated from `cargo metadata --locked --format-version 1` by
`scripts/audit_cargo_licenses.py`. It records every locked workspace and
transitive package, version, Cargo-declared SPDX expression, source, and the
branch selected by SDM's metadata policy. For `OR` expressions the policy
selects MIT when present; conjunctions remain conjunctive. `MIT/Apache-2.0` is
normalized as `MIT OR Apache-2.0`.

The inventory is a review aid. It does not inspect source headers or license
texts, validate that a package's declared expression is accurate, select a
dual-license branch on behalf of a copyright holder, determine compatibility,
or satisfy attribution/notice obligations. Before registry distribution, a
qualified human/legal reviewer must verify actual package license files,
copyright notices, the selected terms, and redistribution obligations. This
review has not occurred; crates.io publication is blocked pending that
sign-off. The license audit is not legal clearance.

Per-crate packaged paths are recorded in
[`package-files.json`](package-files.json) and checked by
`scripts/audit_package_contents.py`. The inventory confirms that current
archives contain source/manifests and intended examples, with no fixtures,
artifacts, build output, credentials, or private datasets.

SDM is MIT licensed and retains the inherited Anomalyco MIT attribution from
the extracted CodeGG semantic core. Third-party crates remain under their
respective owners' licenses. Package archive contents are separately checked
in CI; no training datasets, build outputs, credentials, or private user data
are intended for crate distribution.

# Security Policy

Trendradar is designed for a private, single-administrator deployment. Keep the application behind HTTPS, do not expose PostgreSQL publicly, and store credentials only in server configuration or the ignored `.local/` directory.

Do not open a public issue containing API keys, passwords, database dumps, feed credentials, private article content, host inventories, or production logs. If a report requires sensitive evidence, contact the repository owner privately through their GitHub profile before sharing details.

Only the latest `master` revision receives security fixes. Before reporting a vulnerability, reproduce it against that revision without using production data.

---
title: HelixFlow Platform — Product and Architecture Overview
kind: product
---
# Hosting and data residency
HelixFlow is operated as a multi-tenant software-as-a-service platform hosted exclusively in the European Union, in data centres in Frankfurt am Main (primary) and Dublin (backup). All customer data remains within the European Union.

# Availability
HelixFlow is offered with a contractual availability of 99.9% per calendar month, excluding announced maintenance windows. Availability is monitored externally and reported monthly.

# Security
All data is encrypted at rest with AES-256 and in transit with TLS 1.3. Encryption keys are managed in a hardware-backed key management service. Role-based access control restricts every function and data object. HelixFlow keeps a complete, tamper-evident audit log of all user and administrator actions, retained for at least ten years if required.

# Identity and access
HelixFlow supports single sign-on via SAML 2.0 and OpenID Connect, including Microsoft Entra ID and Keycloak. Multi-factor authentication is enforced for administrators.

# Integration
HelixFlow provides a documented REST API with OpenAPI specifications, outbound webhooks and prebuilt connectors for SAP, Microsoft 365 and common document management systems.

# Backup and recovery
Backups are taken continuously with a recovery point objective (RPO) of 1 hour and a recovery time objective (RTO) of 4 hours. Restores are tested quarterly.

# Accessibility and languages
The citizen and caseworker interfaces conform to WCAG 2.1 level AA. The user interface is available in German and English.

# Scalability
The platform scales horizontally; production tenants serve up to 5,000 concurrent caseworkers.

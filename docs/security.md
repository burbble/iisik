# Security architecture - Lab 5

## Request flow

1. Client sends `login` GraphQL Mutation to Gateway.
2. Gateway forwards credentials to Auth Service over REST.
3. Auth Service verifies PBKDF2 password hash in `identity.db`.
4. Auth Service creates session ID and stores session in Redis with TTL.
5. Auth Service issues JWT containing `sub`, `sid`, `roles`, `iat`, `exp` and returns it through Gateway.
6. Client sends `Authorization: Bearer <JWT>` on protected GraphQL requests.
7. Gateway calls `GET /auth/verify`.
8. Auth Service verifies JWT, checks session in Redis and reloads current roles from Identity storage.
9. Gateway puts verified `Actor` into GraphQL context.
10. Resolver passes `Actor` to `ApplicationFacade`, where role checks are executed before business state changes.

## Role matrix

| Operation | ANALYST | PRODUCTION_ACCOUNTANT | FINANCE_ACCOUNTANT | MANAGER | ADMIN |
|---|---|---|---|---|---|
| products | yes | yes | yes | yes | yes |
| profitability / summary | yes | no | no | yes | yes |
| costBreakdown | yes | no | no | yes | yes |
| importRuns | yes | yes | yes | no | yes |
| startProductionImport | no | yes | no | no | yes |
| startFinancialImport | no | no | yes | no | yes |
| retryImport | by import type | by production import | by finance import | no | yes |
| resolveExternalMapping | no | yes | yes | no | yes |
| calculateCost | yes | no | no | no | yes |
| calculateProfitability | yes | no | no | no | yes |
| exportReport | yes | no | no | yes | yes |

`ADMIN` is treated as a super-role in the implementation.

## Session rule

A syntactically valid JWT is not sufficient. `AuthService.verify()` additionally requires the `sid` session to exist in Redis. Logout deletes the session, while Redis TTL expires it automatically. Therefore a previously issued token stops being accepted when its active session disappears.

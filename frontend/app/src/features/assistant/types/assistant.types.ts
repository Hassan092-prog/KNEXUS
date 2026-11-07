/**
 * Assistant (query) contracts for feature code. Shapes are inferred once in
 * `lib/api/contracts.ts` (mirroring `contracts/phase1/models.py`: QueryRequest,
 * QueryResponse, Citation, QueryMeta) and aliased here — verified against
 * `backend/app/api/v1/endpoints/query.py`. No invented fields.
 */
export type {
  Citation,
  QueryRequest,
  QueryResponse,
  ApiErrorCode,
  ApiErrorResponse,
} from "@/lib/api/contracts"

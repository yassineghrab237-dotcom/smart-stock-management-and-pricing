export interface Identity {
  brand: string;
  manufacturer_ref: string;
  gtin: string;
  variant: string;
  version: number;
}
export interface Watch {
  id: number;
  retailer: string;
  source_url: string;
  interval_hours: number;
  enabled: number;
  version: number;
  next_due: string;
}
export interface CollectedOffer {
  name: string;
  brand: string;
  manufacturer_ref: string;
  merchant_sku: string;
  gtin: string;
  price: string;
  currency: string;
  tax_basis: string;
  availability: string;
  source_url: string;
  observed_at: string;
  content_sha256: string;
  robots_sha256: string;
  parser_version: string;
}
export interface Job {
  id: number;
  watch_id: number;
  retailer: string;
  source_url: string;
  status: string;
  message: string;
  created_at: string;
  result: CollectedOffer | null;
  review_state: string;
  observation_id: number | null;
}
export interface CollectionState {
  identity: Identity | null;
  watches: Watch[];
  jobs: Job[];
  worker_running: boolean;
  events: {
    id: number;
    detail: string;
    actor_name: string;
    created_at: string;
  }[];
}

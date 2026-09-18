-- ============================================================================
-- ACC Livestock Planner - DATA CLASSIFICATION + ABAC
-- 1. Column tags  -> data classification (commercial sensitivity tier)
-- 2. Masking UDFs  -> attribute-based access control bound to persona groups
-- 3. SET MASK      -> enforce on base tables (gold views inherit)
--
-- Persona policy (groups: acc_exec, acc_procurement, acc_operations):
--   Executive   : sees everything (baseline)
--   Procurement : sees pricing (price_per_kg, price_variation, buyer_payee_details)
--   Operations  : sees booking logistics, but pricing/payee terms are masked
--   (no group)  : every governed column is masked
-- ============================================================================

CREATE OR REPLACE FUNCTION project_command_centre.acc_gold.mask_str_proc(v STRING)
RETURNS STRING
COMMENT 'Unmask for Executive or Procurement personas; otherwise redact (commercial pricing terms)'
RETURN CASE WHEN is_member('acc_exec') OR is_member('acc_procurement')
            THEN v ELSE 'REDACTED' END;

-- ---- Data classification tags --------------------------------------------
ALTER TABLE project_command_centre.acc_booking.cattle_bookings ALTER COLUMN price_per_kg SET TAGS ('acc_classification'='restricted','acc_pii_category'='commercial_pricing');
ALTER TABLE project_command_centre.acc_booking.cattle_bookings ALTER COLUMN price_variation SET TAGS ('acc_classification'='restricted','acc_pii_category'='commercial_pricing');
ALTER TABLE project_command_centre.acc_booking.cattle_bookings ALTER COLUMN buyer_payee_details SET TAGS ('acc_classification'='restricted','acc_pii_category'='payment_terms');

-- ---- Apply masks (ABAC enforcement) --------------------------------------
ALTER TABLE project_command_centre.acc_booking.cattle_bookings ALTER COLUMN price_per_kg SET MASK project_command_centre.acc_gold.mask_str_proc;
ALTER TABLE project_command_centre.acc_booking.cattle_bookings ALTER COLUMN price_variation SET MASK project_command_centre.acc_gold.mask_str_proc;
ALTER TABLE project_command_centre.acc_booking.cattle_bookings ALTER COLUMN buyer_payee_details SET MASK project_command_centre.acc_gold.mask_str_proc;

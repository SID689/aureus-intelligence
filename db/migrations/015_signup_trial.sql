-- =====================================================================
-- 015: free trial on signup, and one definition of "currently entitled"
-- =====================================================================
-- New accounts are provisioned on a trial of a paid tier rather than on
-- the free plan (see SIGNUP_TRIAL_TIER / SIGNUP_TRIAL_DAYS in
-- app/core/config.py). A trial is an ordinary user_subscriptions row
-- with status 'trialing' and current_period_end set to when it runs out.
--
-- That makes expiry a real question for the first time. Until now every
-- row with status 'active' or 'trialing' entitled its owner forever,
-- because nothing ever set an end date, and eight different queries
-- spread across the codebase each spelled that rule out by hand:
--
--     WHERE us.status IN ('active', 'trialing')
--
-- Eight copies of a rule that is about to gain a clause is eight chances
-- to forget one, and forgetting one means a lapsed trial keeps unlocking
-- whichever feature that query guards. So the rule moves here, once, and
-- the queries select from this view instead.
--
-- Columns are listed explicitly rather than SELECT *, so adding a column
-- to user_subscriptions later is a deliberate decision about whether the
-- view should carry it, not a silent change.
-- =====================================================================

CREATE OR REPLACE VIEW active_user_subscriptions AS
SELECT
    id,
    user_id,
    tier_id,
    stripe_customer_id,
    stripe_subscription_id,
    status,
    current_period_start,
    current_period_end,
    cancel_at_period_end,
    created_at,
    updated_at
  FROM user_subscriptions
 WHERE status IN ('active', 'trialing')
   -- A paid subscription is governed by Stripe: while its status says
   -- active it is live, whatever the period dates say, because Stripe
   -- moves the status itself when a payment fails. Only trials expire on
   -- a date we set, so only trials are date-checked here.
   AND (
        status <> 'trialing'
     OR current_period_end IS NULL
     OR current_period_end > now()
   );

COMMENT ON VIEW active_user_subscriptions IS
  'Subscriptions that currently entitle their owner. Excludes trials past current_period_end. Every entitlement lookup should read this, not user_subscriptions.';

-- Expiry is evaluated on every gated request, so the lookup wants to be
-- an index hit rather than a scan of a growing table.
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_status
  ON user_subscriptions(user_id, status);

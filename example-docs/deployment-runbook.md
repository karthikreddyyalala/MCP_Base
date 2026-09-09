# Deployment Runbook

## Pre-deploy checklist

- [ ] All tests passing on CI
- [ ] Staging deploy verified by QA
- [ ] Feature flags configured in LaunchDarkly

## Deploy steps

1. Merge PR to main
2. GitHub Actions triggers deploy pipeline
3. Monitor Datadog dashboard for error rate spike (threshold: >1% over 5 min)
4. If error rate spikes, run rollback: `./scripts/rollback.sh <previous-sha>`

## Rollback

```bash
./scripts/rollback.sh abc1234
```

This redeploys the previous image tag. Takes ~3 minutes. Notify #incidents in Slack.

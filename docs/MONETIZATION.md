# Monetization plan for Saad

## What to sell

Sell a narrow service: **“Connect existing electrical telemetry to an assistant that explains readings and prepares maintenance records.”** The customer pays for integration, reliable operation and support. An MCP server is the technical delivery layer.

Start by interviewing a small factory maintenance manager or an electrical automation integrator who already has digital meters/gateways. Ask which readings staff copy manually, which reports take time, what interfaces exist, who approves installations and who controls the budget. Hardware installation is a separate qualified contractor's scope.

## Offers and experimental pricing

These PKR figures are starting quote hypotheses, not verified market rates or promised earnings. Adjust after discovery and estimating labor. Hardware, travel, taxes, paid model usage and third-party licenses are excluded and should be quoted explicitly.

| Offer | Example boundary | Proposed price to test |
|---|---|---|
| Paid pilot | One supported HTTP gateway, up to three devices, local assistant demo, documented findings over two weeks | PKR 15,000–30,000 once |
| Integration setup | One site, agreed device schema, customer-side installation, training and handover after pilot acceptance | PKR 40,000–100,000 once |
| Support subscription | Agreed operating hours, two support hours/month, updates and backup checks; extra work billed separately | PKR 8,000–20,000/month |
| Custom connector | Specific ERP or industrial protocol adapter | Quote after API/register-map review |

A deployed hosted service requires additional engineering before it is sold. This repository does not yet implement remote authentication, hosting operations, automatic backups or uptime monitoring. Charge for those services only once delivered and supported. Do not promise 24/7 response or uptime guarantees as a solo developer without coverage.

Subscription and self-managed licensing models exist in adjacent industrial/IoT products; ThingsBoard describes monthly and perpetual options in its [official product page](https://thingsboard.io/products/thingsboard-pe/) and [January 2026 pricing update](https://thingsboard.io/blog/new-thingsboard-tbmq-pricing-modular-add-ons-top-ups-and-total-cost-clarity/). That validates possible billing structures, not demand or pricing for this project. Sources checked September 13, 2026.

## Revenue is not profit

Illustrative scenario only: three customers at PKR 10,000/month produce PKR 30,000 monthly revenue. If hosting/tools total PKR 4,000 and six support hours are valued at PKR 1,000/hour, contribution is PKR 20,000 before sales time, development, travel, taxes and other costs. There is no assurance of acquiring three customers.

Minimum sustainable fee should cover hosting + model usage + third-party licenses + expected support labor + incident reserve + margin. Measure these during the pilot. Prefer customer-owned infrastructure/credentials where required by their data policies.

## First-customer plan

1. Choose one problem: manual motor/meter reading checks and maintenance draft preparation.
2. Record a short demo showing simulated values clearly, then a real supported gateway once available.
3. Speak with five relevant local businesses or integration firms; learn their current workflow before quoting.
4. Request a vendor API/register map and sanitized sample payload. Scope one supported site; avoid promising universal device compatibility.
5. Agree on a paid pilot with acceptance criteria: selected devices return correct units/timestamps, disconnections are visible, and retries produce one draft.
6. Measure staff time for the old and new workflow, data coverage and support load. Report measured changes; do not claim energy savings without a defensible baseline.
7. After acceptance, offer installation/training plus monthly support. Ask the customer whether a sanitized case study is permitted.

No customer outreach has been sent. Prepare your demo and choose real prospects yourself before sending proposals.

## Product strategy

Keep customer-specific credentials, data and integrations private. A public demonstration repository may help credibility after choosing a license and reviewing its contents. Potential paid additions include specific gateway adapters, approved ERP dispatch, installation, training, reporting and support. Select licensing deliberately before publishing; no commercial software license is supplied by this starter.

The next useful asset is access to one real device/API and a maintenance manager who can test the workflow. Build the next connector against that verified requirement.

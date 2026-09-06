# eBay API compliance note

Last reviewed: 2026-09-06

This document records a material constraint discovered while reviewing the current eBay Developers Program API License Agreement and Buy API production-access requirements. It is project context, not legal advice.

## Why this matters

The scanner's v0.4 design includes an optional eBay Browse API observatory that would ingest listing data and compare it with Cardmarket/CardTrader sourcing evidence to identify resale opportunities. Before adding eBay production credentials, this use case must be checked against eBay's current API terms.

## Current eBay terms that are relevant

The current API License Agreement states that access to Developer Tools is provided for promoting/facilitating access to and use of eBay Services. It also defines certain APIs that provide market-trend, pricing-strategy, sales-volume, user-behaviour or generated-content information as Restricted APIs, with access specially granted to selected Developers.

Important restrictions in the current agreement include:

- Publicly displayed eBay Content must not be co-mingled with non-eBay content; displayed listing data also has freshness requirements.
- Express prior written permission is required for certain derived statistics, including site-wide statistics, eBay-service performance statistics and average selling price / GMV for an eBay category.
- The Restricted Activities section prohibits using eBay Content, alone or with third-party information, to suggest or model prices for items listed on eBay.
- The Restricted Activities section also prohibits using eBay Services to promote or engage in seller arbitrage. The agreement gives automated repricing and cross-site fulfilment as examples, but the clause is broader than those examples.
- eBay Content may not be used to train machine-learning/AI systems.
- Production use of many Buy APIs is limited to approved partners. eBay states that production access requires an application, business-model review, approvals and contracts; there is no guarantee of approval.

Official references reviewed:

- https://developer.ebay.com/join/api-license-agreement
- https://developer.ebay.com/api-docs/buy/buy-requirements.html
- https://developer.ebay.com/api-docs/buy/buy-overview.html

## Project interpretation / risk status

The current Pokemon Deal Scanner business purpose is to compare acquisition opportunities on sources such as Cardmarket/CardTrader with realistic resale evidence. Using eBay API content as a systematic cross-market arbitrage signal could plausibly fall within the seller-arbitrage restriction, and any eBay-derived pricing tool may require additional permission depending on the exact design and API/data used.

Therefore:

1. Do **not** assume that obtaining ordinary eBay Developer credentials makes the current v0.4 eBay observatory an approved production use case.
2. Do **not** add production eBay API credentials to GitHub Actions until the intended use case is approved or clarified by eBay in writing.
3. Treat the current eBay integration as experimental/dormant until that clarification exists.
4. Prefer Cardmarket EN/NM + Ireland landed cost and CardTrader EN/NM as the automated sourcing core.
5. For ad-hoc deal evaluation, individual publicly available eBay sold/completed examples may still be consulted manually as contextual market evidence, but do not silently turn this into automated bulk eBay data collection or an eBay-powered arbitrage/pricing engine without checking the applicable terms.
6. If eBay grants written approval, update this document with the approval scope and then align the code/config/tests to that scope.

## Registration implication

A rejected eBay Developer account registration should not be treated merely as an email-domain problem. Email/domain reputation may be one factor, but even a successful Developer account registration would not by itself resolve the production-access and permitted-use issues above.

Before retrying registration solely to activate the scanner, first decide whether to seek eBay clarification/approval for this specific use case or leave eBay as a manual contextual source.

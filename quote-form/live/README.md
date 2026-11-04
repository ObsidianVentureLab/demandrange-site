# Live page snapshot

`request-a-quote.html` here is a byte-for-byte copy of the page served at
https://demandrange.com/request-a-quote.html, taken from the public repository's
`main` branch at commit `e460879` (release r20, 3 November 2026).

It is **not** published from this directory and is **not** a build input. It exists so
that the handler (`../apps-script/Code.gs`), the schema (`../form_schema.json`) and the
page the browser actually submits sit in one tree and can be tested together:
`tests/test_regions.js` reads the region checkbox values out of this file and proves the
handler accepts every one of them.

Refresh it from `main` whenever the live form changes, then re-run the quote-form tests.

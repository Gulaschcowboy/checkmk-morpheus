# Contributing

Please report the Checkmk version/edition, Morpheus version, provider type, package version and affected service. Remove customer names, tokens, API keys, passwords and private network identifiers from examples.

Reproduce the problem with a small sanitized fixture and a behavior-focused test. Run:

```bash
python3 -m unittest discover -s tests -v
python3 build.py
```

For changes to public API usage, rule forms, metric expressions or graph definitions, also run `python3 tests/validate_public_api.py` in a Checkmk 2.4 environment, then validate the MKP in a test site.

Document provider-specific metric semantics. Do not turn absent readings into zero, refresh cached timestamps to the current time, or silently normalize CPU by a guessed scale. Avoid changes to service/metric identity without upgrade notes.

Contributions to this release must be compatible with GPL-2.0-only. Preserve existing copyright and license notices. Coordinate substantial changes with the maintainer before opening a large pull request.


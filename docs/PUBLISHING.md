# Publishing 1.1.0

Repository: https://github.com/pwladzinski/checkmk-morpheus

All distributed documentation, examples and configuration text are in English. Each installation supplies its connection settings. No customer-specific site, address, VM prefix or credential is embedded in the package.

## Update the source repository

Extract the source ZIP and upload its contents at the repository root. Keep `src`, `tests`, `docs` and `package` intact. Include `.gitignore` and `.gitattributes`. Review the diff and commit the 1.1.0 fixes. Do not introduce a duplicate versioned source directory. Do not upload site exports, raw API responses or credentials.

## Test the exact asset

Install `package/morpheus-1.1.0.mkp` on the target Checkmk 2.4 test site. Follow [UPGRADE_1.1.0.md](UPGRADE_1.1.0.md), including `cmk-validate-plugins`, discovery and failure/recovery checks. Local tests and public API validation are not a substitute for live validation.

## GitHub release

1. Create tag `v1.1.0` from the reviewed source commit.
2. Use title `HPE Morpheus Monitoring 1.1.0`.
3. Paste [RELEASE_NOTES_1.1.0_EN.md](RELEASE_NOTES_1.1.0_EN.md).
4. Attach `morpheus-1.1.0.mkp` and `SHA256SUMS.txt` from `package/`.
5. Verify the attachments against the checksum before publishing.

The supplied MKP metadata includes the public project URL. Do not silently replace a published MKP with different bytes under the same version.

## Checkmk Exchange

On the existing package page choose **Add Version**, upload the MKP (not the ZIP) and provide the release description. Keep the same package identity and maintainer attribution. Review the terms and submit for moderation. A submission under review is not yet approved or publicly available.

Description: [EXCHANGE_DESCRIPTION_EN.md](EXCHANGE_DESCRIPTION_EN.md).

References:

- https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- https://exchange.checkmk.com/how-to-upload

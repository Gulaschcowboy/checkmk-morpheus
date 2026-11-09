# Publishing and repository layout

Repository: https://github.com/pwladzinski/checkmk-morpheus

All distributed documentation, examples and configuration text are in English. Connection settings are provided by each installation; no customer-specific site, appliance address, VM prefix or credential is embedded in the package. The maintainer's public name and email remain in the license/source metadata.

## Replace the initially uploaded directory

The initial GitHub upload put the entire distribution bundle inside a versioned directory. The English-only replacement ZIP is laid out as the repository root itself.

1. Extract the replacement ZIP locally.
2. Open the main repository page, choose **Add file → Upload files**, and upload the contents of the extracted directory directly into the repository root. Do not upload a wrapping versioned directory or the ZIP itself.
3. Keep the `src`, `tests`, `docs` and `package` directories intact. Include `.gitignore` and `.gitattributes`; on macOS, **Command + Shift + .** shows hidden files in Finder. Add those two files separately through **Add file → Create new file** if the uploader skips them.
4. Review the upload and commit with the message `Use English-only documentation and root repository layout`.
5. Open the old `Morpheus_Checkmk_2.4_MKP_1.0.4` directory on GitHub. Use the directory's **… → Delete directory** action, review the removed paths, and commit. This removes the duplicate layout and the old language-specific files from the current tree.
6. Confirm that the root README renders the project documentation and that only the root-level source tree remains.

Deleting old paths from the current tree does not rewrite historical commits. No repository history rewrite is included in this workflow.

GitHub documentation:

- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- https://docs.github.com/en/repositories/working-with-files/managing-files/deleting-files-in-a-repository

## Installable asset and version

`package/morpheus-1.0.4.mkp` is unchanged by this documentation cleanup. Its existing SHA-256 checksum still applies. No new monitoring version, service identity or metric identity is introduced.

Only English documentation and generic configuration examples belong in the source repository. Do not commit a site export, a live API response, tokens, passwords or private appliance addresses.

## Create the GitHub release

1. Open **Releases → Draft a new release**.
2. Create tag `v1.0.4` for the reviewed `main` branch.
3. Set the release title to `HPE Morpheus Monitoring 1.0.4`.
4. Paste [RELEASE_NOTES_1.0.4_EN.md](RELEASE_NOTES_1.0.4_EN.md).
5. Attach `morpheus-1.0.4.mkp` and `SHA256SUMS.txt` from `package/`.
6. Review and save a draft or publish the release.

https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository

The repository URL is already present in the README and Exchange description. The supplied MKP's Download-URL field remains empty to preserve the exact installation asset. If you want to add the repository URL to the MKP metadata, rebuild it **before** publishing the asset:

```bash
python3 build.py --download-url https://github.com/pwladzinski/checkmk-morpheus
cd dist
sha256sum morpheus-1.0.4.mkp > SHA256SUMS.txt
```

On macOS, use `shasum -a 256` instead of `sha256sum`. Replace both release attachments together. Do not silently replace a published installation asset with different bytes under the same version; use a new release version for later changes.

## Validate before Exchange submission

Install the exact MKP into a Checkmk 2.4 test site. As the site user:

```bash
mkp inspect ~/morpheus-1.0.4.mkp
mkp add ~/morpheus-1.0.4.mkp
mkp enable morpheus 1.0.4
cmk-validate-plugins
```

Verify live collection, discovery, thresholds, VM piggyback and graph rendering. Local unit tests/public API validation are not a substitute for testing the exact archive on a site.

## Submit to Checkmk Exchange

1. Register a separate account at https://exchange.checkmk.com/ and verify its email address.
2. Choose **Upload new package**.
3. Upload `package/morpheus-1.0.4.mkp`, not the source ZIP.
4. Paste [EXCHANGE_DESCRIPTION_EN.md](EXCHANGE_DESCRIPTION_EN.md).
5. Choose a suitable built-in infrastructure/cloud icon.
6. Review the terms and submit the package for moderation.
7. Submit subsequent releases on the same package page through **Add Version**.

No GitHub or Exchange credentials need to be shared with the maintainer or included in the repository. No vendor logos or private installation screenshots are bundled.

https://exchange.checkmk.com/how-to-upload


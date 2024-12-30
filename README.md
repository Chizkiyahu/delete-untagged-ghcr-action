# delete-untagged-ghcr-action 
[![test](https://github.com/Chizkiyahu/delete-untagged-ghcr-action/actions/workflows/test.yml/badge.svg)](https://github.com/Chizkiyahu/delete-untagged-ghcr-action/actions/workflows/test.yml)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/94534b5b1d7c4c938149bde7dc6d18e2)](https://www.codacy.com/gh/Chizkiyahu/delete-untagged-ghcr-action/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Chizkiyahu/delete-untagged-ghcr-action&amp;utm_campaign=Badge_Grade)

Action for delete containers from Github container registry

delete all / untagged ghcr containers in a repository
## Usage

<!-- start usage -->
```yaml
- name: Delete untagged ghcr
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
    # Personal access token (PAT) used to fetch the repository. The PAT is configured
    # with the local git config, which enables your scripts to run authenticated git
    # commands. The post-job step removes the PAT.
    # needs delete:packages permissions
    # required: true
    # [Learn more about creating and using encrypted secrets](https://help.github.com/en/actions/automating-your-workflow-with-github-actions/creating-and-using-encrypted-secrets)
    token: ${{ secrets.PAT_TOKEN }}
    # Repository name or  name with owner
    # Delete only from repository name
    # Default: ${{ github.repository }}
    repository: ''
    # 'The repository owner name'
    # Default: ${{ github.repository_owner }}
    repository_owner: ''
    # 'The package names'
    # Delete only from comma separated package names
    # required: false
    package_name: ''
    # Delete only package versions without tag
    # required: false
    # Default: true
    # choices: true, false
    untagged_only: true
    # Exclude untagged multiplatform packages from deletion
    # Manifests are usually such packages so they should be excluded
    # only for untagged_only=true
    # Default: true
    # needs docker installed
    except_untagged_multiplatform: true
    # Include signatures corresponding to deleted packages
    # without tags. Signature has the `sha256-<digest>.sig` tag where 
    # respective untagged package has `sha256:<digest>` name
    # required: false
    # default: false
    with_sigs: true
    # The owner type
    # required: true
    # choices: org, user
    owner_type: ''
```
<!-- end usage -->

## Scenarios
- [Delete all owner containers without tags](#delete-all-owner-containers-without-tags)
- [Delete all owner containers](#delete-all-owner-containers)
- [Delete all containers from repository without tags](#delete-all-containers-from-repository-without-tags)
- [Delete all containers from repository](#delete-all-containers-from-repository)
- [Delete all containers from package without tags](#delete-all-containers-from-package-without-tags)
- [Delete all containers from package with signatures](#delete-all-containers-from-package-without-tags-and-corresponding-tagged-signatures)
- [Delete all containers from package](#delete-all-containers-from-package)

## Delete all owner containers without tags
```yaml
- name: Delete all owner containers without tags
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
      token: ${{ secrets.PAT_TOKEN }}
      repository_owner: ${{ github.repository_owner }}
      owner_type: org # or user
```

## Delete all owner containers
```yaml
  - name: Delete all owner containers
    uses: Chizkiyahu/delete-untagged-ghcr-action@v5
    with:
        token: ${{ secrets.PAT_TOKEN }}
        repository_owner: ${{ github.repository_owner }}
        untagged_only: false
        owner_type: org # or user
```

## Delete all containers from repository without tags
```yaml
  - name: Delete all containers from repository without tags
    uses: Chizkiyahu/delete-untagged-ghcr-action@v5
    with:
        token: ${{ secrets.PAT_TOKEN }}
        repository_owner: ${{ github.repository_owner }}
        repository: ${{ github.repository }}
        untagged_only: true
        owner_type: org # or user

```

## Delete all containers from repository without tags except untagged multiplatform packages
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v2
- name: Login to GitHub Container Registry with PAT_TOKEN
  uses: docker/login-action@v2
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.PAT_TOKEN }}
- name: Delete all containers from repository without tags
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
      token: ${{ secrets.PAT_TOKEN }}
      repository_owner: ${{ github.repository_owner }}
      repository: ${{ github.repository }}
      untagged_only: true
      owner_type: org # or user
      except_untagged_multiplatform: true

```


## Delete all containers from repository
```yaml
- name: Delete all containers from repository
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
      token: ${{ secrets.PAT_TOKEN }}
      repository_owner: ${{ github.repository_owner }}
      repository: ${{ github.repository }}
      untagged_only: false
      owner_type: org # or user
```

## Delete all containers from package without tags
```yaml
- name: Delete all containers from package without tags
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
      token: ${{ github.token }}
      repository_owner: ${{ github.repository_owner }}
      repository: ${{ github.repository }}
      package_name: the-package-name
      untagged_only: true
      owner_type: org # or user
```

## Delete all containers from package without tags except untagged multiplatform packages
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v2
- name: Login to GitHub Container Registry with PAT_TOKEN
  uses: docker/login-action@v2
  with:
    registry: ghcr.io
    username: ${{ github.repository_owner }}
    password: ${{ github.token }}
- name: Delete all containers from package without tags
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
      token: ${{ github.token }}
      repository_owner: ${{ github.repository_owner }}
      repository: ${{ github.repository }}
      package_name: the-package-name
      untagged_only: true
      owner_type: org # or user
      except_untagged_multiplatform: true
```

## Delete all containers from package without tags and corresponding tagged signatures

> [!IMPORTANT]
> This option has been tested with v3.7.0 [`cosign-installer`][cos-inst] action
> using `cosign-release` v2.4.1. See [workflow](.github/workflows/reusable.yml)
> for example ("Install cosign" and "Sign the published Docker image" steps).

[cos-inst]: https://github.com/sigstore/cosign-installer

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v2
- name: Login to GitHub Container Registry with PAT_TOKEN
  uses: docker/login-action@v2
  with:
    registry: ghcr.io
    username: ${{ github.repository_owner }}
    password: ${{ github.token }}
- name: Delete all containers from package without tags
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
      token: ${{ github.token }}
      repository_owner: ${{ github.repository_owner }}
      repository: ${{ github.repository }}
      package_name: the-package-name
      untagged_only: true
      with_sigs: true
      owner_type: org # or user
```

## Delete all containers from packages
```yaml
- name: Delete all containers from package
  uses: Chizkiyahu/delete-untagged-ghcr-action@v5
  with:
      token: ${{ github.token }}
      repository_owner: ${{ github.repository_owner }}
      repository: ${{ github.repository }}
      package_name: the-package-name, other-package-name
      untagged_only: false
      owner_type: org # or user
```

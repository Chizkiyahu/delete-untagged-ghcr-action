import json
import os
import subprocess
import urllib.parse

import requests
import argparse
import logging

API_ENDPOINT = "https://api.github.com"
PER_PAGE = 100  # max 100 defaults 30
DOCKER_ENDPOINT = "ghcr.io/"

logger = logging.getLogger(__name__)


class NoManifestErr(Exception):
    pass


def get_url(path):
    if path.startswith(API_ENDPOINT):
        return path
    return f"{API_ENDPOINT}{path}"


def get_base_headers():
    return {
        "Authorization": f"token {args.token}",
        "Accept": "application/vnd.github.v3+json",
    }


def del_req(path):
    url = get_url(path)
    logger.debug(f"DELETE {url}")
    res = requests.delete(url, headers=get_base_headers())
    logger.debug(f"-> {res.status_code} {res.text.strip()}", )
    if res.ok:
        logger.info(f"Deleted {path}")
    else:
        logger.error(f"Error when trying to delete URL: {url} MSG: {res.text}")
    return res


def get_req(path, params=None):
    if params is None:
        params = {}
    params.update(page=1)
    if "per_page" not in params:
        params["per_page"] = PER_PAGE
    url = get_url(path)
    result = []
    while True:
        logger.debug("GET %s params=%s", url, params)
        response = requests.get(url, headers=get_base_headers(), params=params)
        logger.debug("-> %s %s", response.status_code,
                     response.text.strip() if not response.ok else "ok")
        if not response.ok:
            raise Exception(response.text)
        result.extend(response.json())

        if "next" not in response.links:
            break
        url = response.links["next"]["url"]
        if "page" in params:
            del params["page"]
    return result


def get_list_packages(owner, repo_name, owner_type, package_names):
    pkgs = []
    if package_names:
        for package_name in package_names:
            clean_package_name = urllib.parse.quote(package_name, safe='')
            url = get_url(
                f"/{owner_type}s/{owner}/packages/container/{clean_package_name}"
            )
            logger.debug(f"GET {url}")
            response = requests.get(url, headers=get_base_headers())
            logger.debug(
                f"-> {response.status_code} {response.text.strip() if not response.ok else 'ok'}"
            )
            if not response.ok:
                if response.status_code == 404:
                    return []
                raise Exception(response.text)
            pkgs.append(response.json())
    else:
        pkgs = get_req(
            f"/{owner_type}s/{owner}/packages?package_type=container")

    # this is a strange bug in github api, it returns deleted packages
    # I open a ticket for that
    pkgs = [pkg for pkg in pkgs if not pkg["name"].startswith('deleted_')]
    if repo_name:
        pkgs = [
            pkg for pkg in pkgs if pkg.get("repository")
            and pkg["repository"]["name"].lower() == repo_name
        ]
    logger.debug("Packages found: %s", [pkg.get("name") for pkg in pkgs])
    return pkgs


def get_all_package_versions(owner, repo_name, package_names, owner_type):
    packages = get_list_packages(
        owner=owner,
        repo_name=repo_name,
        package_names=package_names,
        owner_type=owner_type,
    )
    return {
        pkg['name']: get_all_package_versions_per_pkg(pkg["url"])
        for pkg in packages
    }


def get_all_package_versions_per_pkg(package_url):
    url = f"{package_url}/versions"
    versions = get_req(url)
    logger.debug(
        f"Versions for {package_url}: {[v.get('name') for v in versions]}")
    return versions


def get_deps_pkgs(owner, pkgs):
    ids = []
    successful = True
    login_into_registry(owner)
    for pkg in pkgs:
        for pkg_ver in pkgs[pkg]:
            try:
                image = f"{DOCKER_ENDPOINT}{owner}/{pkg}@{pkg_ver['name']}"
                logger.debug(f"Inspect image {image}")
                ids.extend(get_image_deps(image))
            except Exception as e:
                print(e)
                successful = False
    if not successful:
        raise Exception("Error on image dependency resolution")
    return ids


def login_into_registry(owner):
    cmd = f"docker login ghcr.io -u {owner} --password {args.token}"
    logger.debug(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True)
    logger.debug(f"-> return code {res.returncode}")
    if res.returncode != 0:
        print(cmd)
        raise Exception(res.stderr)


def get_image_deps(image):
    try:
        manifest_txt = get_manifest(image)
        logger.debug(f"Manifest for {image}: {manifest_txt.strip()}")
        data = json.loads(manifest_txt)
        return [manifest["digest"] for manifest in data.get("manifests", [])]
    except NoManifestErr:
        return []


def get_manifest(image):
    cmd = f"docker manifest inspect {image}"
    logger.debug(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True)
    logger.debug(f"-> return code {res.returncode}")
    if res.returncode != 0:
        print(cmd)
        if res.stderr == b"manifest unknown\n":
            raise NoManifestErr()
        raise Exception(res.stderr)
    return res.stdout.decode("utf-8")


def delete_pkgs(owner, repo_name, owner_type, package_names, untagged_only,
                except_untagged_multiplatform, with_sigs, dry_run):
    if untagged_only:
        all_packages = get_all_package_versions(
            owner=owner,
            repo_name=repo_name,
            package_names=package_names,
            owner_type=owner_type,
        )
        tagged_pkgs = {
            pkg: [
                pkg_ver for pkg_ver in all_packages[pkg]
                if pkg_ver["metadata"]["container"]["tags"]
            ]
            for pkg in all_packages
        }
        if except_untagged_multiplatform:
            deps_pkgs = get_deps_pkgs(owner, tagged_pkgs)
        else:
            deps_pkgs = []
        all_packages = [
            pkg_ver for pkg in all_packages for pkg_ver in all_packages[pkg]
        ]
        packages = [
            pkg for pkg in all_packages
            if not pkg["metadata"]["container"]["tags"]
            and pkg["name"] not in deps_pkgs
        ]
        logger.debug(
            f"Packages to delete (untagged): {[p['url'] for p in packages]}")
        if with_sigs:
            digests = {
                sha[1]
                for pkg in packages if len(sha := pkg["name"].split(":")) == 2
            }
            old_signed = [
                pkg for pkg in all_packages if {
                    sha[1].removesuffix(".sig")
                    for tag in pkg["metadata"]["container"]["tags"]
                    if tag and len(sha := tag.split("-")) == 2
                } & digests
            ]
            packages += old_signed
    else:
        packages = get_list_packages(
            owner=owner,
            repo_name=repo_name,
            package_names=package_names,
            owner_type=owner_type,
        )
    logger.debug(f"Packages to delete: {[p.get('url') for p in packages]}")
    if dry_run:
        for pkg in packages:
            print(f"DRY RUn delete {pkg['url']}")
        status = [True] * len(packages)
    else:
        status = [del_req(pkg["url"]).ok for pkg in packages]
    len_ok = len([ok for ok in status if ok])
    len_fail = len(status) - len_ok

    logger.info(f"Deleted {len_ok} package")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"num_deleted={len_ok}\n")
    if len_fail > 0:
        raise Exception(f"fail delete {len_fail}")


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--token",
        type=str,
        required=True,
        help="GitHub Personal access token with delete:packages permissions",
    )
    parser.add_argument("--repository_owner",
                        type=str,
                        required=True,
                        help="The repository owner name")
    parser.add_argument(
        "--repository",
        type=str,
        required=False,
        default="",
        help="Delete only repository name",
    )
    parser.add_argument(
        "--package_names",
        type=str,
        required=False,
        default="",
        help="Delete only comma separated package names",
    )
    parser.add_argument(
        "--untagged_only",
        type=str2bool,
        help="Delete only package versions without tag",
    )
    parser.add_argument(
        "--owner_type",
        choices=["org", "user"],
        default="org",
        help="Owner type (org or user)",
    )
    parser.add_argument(
        "--except_untagged_multiplatform",
        type=str2bool,
        help=
        "Except untagged multiplatform packages from deletion (only for --untagged_only) needs docker installed",
    )
    parser.add_argument("--with_sigs",
                        type=str2bool,
                        help="Delete old signatures")
    parser.add_argument("--dry_run",
                        type=str2bool,
                        help="Dry run, do not delete anything")
    parser.add_argument("--debug",
                        type=str2bool,
                        default=False,
                        help="Enable debug output")
    args = parser.parse_args()
    if os.getenv("ACTIONS_STEP_DEBUG", "").lower() == "true":
        args.debug = True
    if "/" in args.repository:
        repository_owner, repository = args.repository.split("/")
        if repository_owner != args.repository_owner:
            raise Exception(
                f"Mismatch in repository:{args.repository} and repository_owner:{args.repository_owner}"
            )
        args.repository = repository
    args.repository = args.repository.lower()
    args.repository_owner = args.repository_owner.lower()
    args.package_names = args.package_names.lower()
    args.package_names = [p.strip() for p in args.package_names.split(",")
                          ] if args.package_names else []
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(message)s")
    return args


if __name__ == "__main__":
    args = get_args()
    delete_pkgs(
        owner=args.repository_owner,
        repo_name=args.repository,
        package_names=args.package_names,
        untagged_only=args.untagged_only,
        owner_type=args.owner_type,
        except_untagged_multiplatform=args.except_untagged_multiplatform,
        with_sigs=args.with_sigs,
        dry_run=args.dry_run)

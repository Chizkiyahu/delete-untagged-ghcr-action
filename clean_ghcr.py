import json
import requests
import argparse
from dxf import DXF

API_ENDPOINT = "https://api.github.com"
PER_PAGE = 100  # max 100 defaults 30
DOCKER_ENDPOINT = "ghcr.io"


def get_url(path):
    if path.startswith(API_ENDPOINT):
        return path
    return f"{API_ENDPOINT}{path}"


def get_base_headers():
    return {
        "Authorization": "token {}".format(args.token),
        "Accept": "application/vnd.github.v3+json",
    }


def del_req(path):
    res = requests.delete(get_url(path), headers=get_base_headers())
    if res.ok:
        print(f"Deleted {path}")
    else:
        print(res.text)
    return res


def get_req(path, params=None):
    if params is None:
        params = {}
    params.update(page=1)
    if "per_page" not in params:
        params["per_page"] = PER_PAGE
    url = get_url(path)
    another_page = True
    result = []
    while another_page:
        response = requests.get(url, headers=get_base_headers(), params=params)
        if not response.ok:
            raise Exception(response.text)
        result.extend(response.json())
        if "next" in response.links:
            url = response.links["next"]["url"]
            if "page" in params:
                del params["page"]
        else:
            another_page = False
    return result


def get_list_packages(owner, repo_name, owner_type, package_name):
    all_org_pkg = get_req(
        f"/{owner_type}s/{owner}/packages?package_type=container")
    if repo_name:
        all_org_pkg = [
            pkg for pkg in all_org_pkg if pkg.get("repository")
            and pkg["repository"]["name"].lower() == repo_name
        ]
    if package_name:
        all_org_pkg = [
            pkg for pkg in all_org_pkg if pkg["name"] == package_name
        ]
    return all_org_pkg


def get_all_package_versions(owner, repo_name, package_name, owner_type):
    packages = get_list_packages(
        owner=owner,
        repo_name=repo_name,
        package_name=package_name,
        owner_type=owner_type,
    )
    return {
        pkg['name']: get_all_package_versions_per_pkg(pkg["url"])
        for pkg in packages
    }


def get_all_package_versions_per_pkg(package_url):
    url = f"{package_url}/versions"
    return get_req(url)


def get_deps_pkgs(owner, pkgs):
    ids = []
    for pkg_name, pkg_versions in pkgs.items():
        registry = get_registry(owner, pkg_name)
        for pkg_ver in pkg_versions:
            manifest_txt = registry.get_manifest(pkg_ver['name'])
            ids.extend(get_image_deps(manifest_txt))
    return ids


def get_registry(owner, pkg_name):
    return DXF(
        DOCKER_ENDPOINT,
        repo=f"{owner}/{pkg_name}",
        auth=lambda dxf, resp: dxf.authenticate(owner, args.token, response=resp)
    )


def get_image_deps(manifest_txt):
    data = json.loads(manifest_txt)
    return [manifest['digest'] for manifest in data.get("manifests", [])]


def delete_pkgs(owner, repo_name, owner_type, package_name, untagged_only,
                except_untagged_multiplatform):
    if untagged_only:
        all_packages = get_all_package_versions(
            owner=owner,
            repo_name=repo_name,
            package_name=package_name,
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
    else:
        packages = get_list_packages(
            owner=owner,
            repo_name=repo_name,
            package_name=package_name,
            owner_type=owner_type,
        )
    status = [del_req(pkg["url"]).ok for pkg in packages]
    len_ok = len([ok for ok in status if ok])
    len_fail = len(status) - len_ok
    print(f"Deleted {len_ok} package")
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
        help="Github Personal access token with delete:packages permissions",
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
        "--package_name",
        type=str,
        required=False,
        default="",
        help="Delete only package name",
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
    args = parser.parse_args()
    if "/" in args.repository:
        repository_owner, repository = args.repository.split("/")
        if repository_owner != args.repository_owner:
            raise Exception(
                f"Mismatch in repository:{args.repository} and repository_owner:{args.repository_owner}"
            )
        args.repository = repository
    if args.package_name and args.package_name.count("/") == 2:
        _, repo_name, package_name = args.package_name.split("/")
        package_name = f"{repo_name}/{package_name}"
        args.package_name = package_name
    args.repository = args.repository.lower()
    args.repository_owner = args.repository_owner.lower()
    args.package_name = args.package_name.lower()
    return args


if __name__ == "__main__":
    args = get_args()
    delete_pkgs(
        owner=args.repository_owner,
        repo_name=args.repository,
        package_name=args.package_name,
        untagged_only=args.untagged_only,
        owner_type=args.owner_type,
        except_untagged_multiplatform=args.except_untagged_multiplatform)

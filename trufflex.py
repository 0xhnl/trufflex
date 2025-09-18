#!/usr/bin/env python3
import sys
import requests
import subprocess
import json
import argparse
import pandas as pd
import os
from urllib.parse import urlparse
from time import sleep
import yaml

YELLOW = "\033[93m"
RESET = "\033[0m"

# ------------------------
# Utility functions
# ------------------------

def read_credentials():
    """Read GitHub token and Docker credentials from cred.conf"""
    if not os.path.exists("cred.conf"):
        print("Error: cred.conf file not found.")
        sys.exit(1)
    with open("cred.conf", "r") as f:
        try:
            conf = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error parsing cred.conf: {e}")
            sys.exit(1)
    github_token = None
    docker_user = docker_pass = None

    if "github" in conf and conf["github"]:
        github_token = conf["github"][0].strip()
    if "docker" in conf and conf["docker"]:
        line = conf["docker"][0].strip()
        if ":" not in line:
            print("Error: Docker credentials must be in format username:password")
            sys.exit(1)
        docker_user, docker_pass = line.split(":", 1)
    return github_token, docker_user, docker_pass

def run_trufflehog(cmd):
    """Run a trufflehog command and capture output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout + result.stderr
    except FileNotFoundError:
        print("Error: trufflehog not found. Install it with: pip install trufflehog")
        sys.exit(1)

# ------------------------
# GitHub functions
# ------------------------

def get_user_repos(token):
    headers = {'Authorization': f'token {token}'}
    repos = []
    url = 'https://api.github.com/user/repos'
    params = {'per_page': 100, 'type': 'owner'}
    while url:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code != 200:
            break
        data = r.json()
        repos.extend([f"https://github.com/{repo['full_name']}" for repo in data])
        url = r.links.get('next', {}).get('url')
        params = None
    return repos

def get_orgs(token):
    headers = {'Authorization': f'token {token}'}
    orgs = []
    url = 'https://api.github.com/user/orgs'
    while url:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            break
        data = r.json()
        orgs.extend([org['login'] for org in data])
        url = r.links.get('next', {}).get('url')
    return orgs

def get_profile_repos(profile_url, token=None):
    username = urlparse(profile_url).path.strip("/")
    if not username:
        print(f"Invalid profile URL: {profile_url}")
        return []
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    repos = []
    url = f'https://api.github.com/users/{username}/repos'
    params = {'per_page': 100}
    while url:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code != 200:
            print(f"Failed to fetch repos for {username}: {r.status_code}")
            break
        data = r.json()
        repos.extend([f"https://github.com/{repo['full_name']}" for repo in data])
        url = r.links.get('next', {}).get('url')
        params = None
    return repos

def scan_my_repos_and_orgs(token):
    print("=== STEP 1: Fetching my repositories and organizations ===")
    repos = get_user_repos(token)
    orgs = get_orgs(token)
    with open('personal.txt', 'w') as f:
        if repos:
            f.write('\n'.join(sorted(repos)))
        else:
            f.write("No personal repositories found.")
    with open('org.txt', 'w') as f:
        if orgs:
            f.write('\n'.join(sorted(orgs)))
        else:
            f.write("No organizations found.")
    all_output = []
    for org in orgs:
        print(f"Scanning organization: {org}")
        cmd = ['trufflehog', 'github', f'--org={org}', f'--token={token}', '--json']
        all_output.append(run_trufflehog(cmd))
    for repo in repos:
        print(f"Scanning repository: {repo}")
        cmd = ['trufflehog', 'github', f'--repo={repo}', f'--token={token}', '--json']
        all_output.append(run_trufflehog(cmd))
    return all_output

def scan_other_repos(file_path):
    with open(file_path, "r") as f:
        repos = [line.strip() for line in f if line.strip()]
    all_output = []
    for repo in repos:
        print(f"Scanning repository: {repo}")
        cmd = ['trufflehog', 'github', f'--repo={repo}', '--json']
        all_output.append(run_trufflehog(cmd))
    return all_output

def scan_profile_repos(file_path, token=None):
    with open(file_path, "r") as f:
        profiles = [line.strip() for line in f if line.strip()]
    all_repos = []
    for profile in profiles:
        repos = get_profile_repos(profile, token)
        print(f"Profile {profile} has {len(repos)} repos")
        all_repos.extend(repos)
    all_output = []
    for repo in all_repos:
        print(f"Scanning repository: {repo}")
        cmd = ['trufflehog', 'github', f'--repo={repo}', '--json']
        all_output.append(run_trufflehog(cmd))
    return all_output

# ------------------------
# Docker functions
# ------------------------

def get_docker_token(username: str, password: str) -> str:
    url = "https://hub.docker.com/v2/users/login/"
    r = requests.post(url, headers={"Content-Type": "application/json"}, json={"username": username, "password": password})
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} {r.text}")
        sys.exit(1)
    return r.json().get("token")

def get_username_from_url(url: str) -> str:
    if "/u/" in url:
        return url.rstrip("/").split("/u/")[-1]
    return url.strip()

def list_repositories(username: str, token: str):
    repos = []
    url = f"https://hub.docker.com/v2/repositories/{username}/"
    headers = {"Authorization": f"JWT {token}"}
    while url:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print(f"Error fetching repositories: {r.status_code} {r.text}")
            sys.exit(1)
        data = r.json()
        for repo in data.get("results", []):
            repos.append(repo["name"])
        url = data.get("next")
    return repos

def dockerhub_tag_endpoint(name, page):
    return f"https://hub.docker.com/v2/repositories/{name}/tags?page_size=100&page={page}"

def skip_tag(tag_name):
    deny_list = [".sig", ".enc"]
    return any(tag_name.endswith(t) for t in deny_list)

def get_container_tag_page(name, page):
    url = dockerhub_tag_endpoint(name, page)
    response = requests.get(url)
    return response.json()

def get_container_tags(name):
    page = 1
    while True:
        response = get_container_tag_page(name, page)
        results = response.get("results", [])
        for result in results:
            yield result
        if not response.get("next"):
            break
        page += 1

def scan_with_trufflehog(image: str):
    try:
        result = subprocess.run(
            ["trufflehog", "docker", "--image", image, "--json", "--only-verified", "--no-update"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False
        )
        findings = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return findings
    except Exception as e:
        print(f"Error scanning {image}: {e}")
        return []

def parse_docker_finding(image: str, finding: dict) -> dict:
    docker_meta = finding.get("SourceMetadata", {}).get("Data", {}).get("Docker", {})
    extra = finding.get("ExtraData") or {}
    return {
        "image": docker_meta.get("image", image),
        "tag": docker_meta.get("tag", ""),
        "layer": docker_meta.get("layer", ""),
        "file": docker_meta.get("file", ""),
        "detector_name": finding.get("DetectorName", ""),
        "detector_type": finding.get("DetectorType", ""),
        "detector_desc": finding.get("DetectorDescription", ""),
        "raw": finding.get("Raw", ""),
        "redacted": finding.get("Redacted", ""),
        "verified": finding.get("Verified", False),
        "rotation_guide": extra.get("rotation_guide", ""),
        "version": extra.get("version", "")
    }

# ------------------------
# Excel export
# ------------------------

def save_to_excel_github(results_file, output_file):
    rows = []
    with open(results_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                github_data = data.get("SourceMetadata", {}).get("Data", {}).get("Github", {})
                rows.append({
                    "DetectorName": data.get("DetectorName", ""),
                    "DetectorDescription": data.get("DetectorDescription", ""),
                    "Verified": data.get("Verified", ""),
                    "RawSecret": data.get("Raw", ""),
                    "Repository": github_data.get("repository", ""),
                    "Commit": github_data.get("commit", ""),
                    "File": github_data.get("file", ""),
                    "Line": github_data.get("line", ""),
                    "Link": github_data.get("link", ""),
                    "Email": github_data.get("email", ""),
                    "Timestamp": github_data.get("timestamp", ""),
                })
            except json.JSONDecodeError:
                continue
    if rows:
        df = pd.DataFrame(rows)
        df.to_excel(output_file, index=False)
        print(f"Parsed GitHub results saved to {output_file} ({len(rows)} findings)")
    else:
        print("No valid GitHub JSON found, Excel not created.")

def save_to_excel_docker(findings, output_file):
    if findings:
        df = pd.DataFrame(findings)
        df.to_excel(output_file, index=False)
        print(f"Parsed Docker results saved to {output_file} ({len(findings)} findings)")
    else:
        print("No Docker findings, Excel not created.")

# ------------------------
# Main
# ------------------------

def main():
    parser = argparse.ArgumentParser(description="TruffleHog combined GitHub + Docker scanner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--git-me", action="store_true")
    group.add_argument("--git-other", action="store_true")
    group.add_argument("--git-profile", action="store_true")
    group.add_argument("--docker-profile", help="Scan all Docker repos under profile")
    group.add_argument("--docker-repo", help="Scan Docker repos from file")
    parser.add_argument("-f", "--file", help="File with list of repos/profiles")
    parser.add_argument("-o", "--output", help="Excel output filename", default="output.xlsx")
    parser.add_argument("--all-tag", action="store_true", help="Scan all tags (Docker only)")
    args = parser.parse_args()

    github_token, docker_user, docker_pass = read_credentials()

    all_output = []
    docker_findings = []

    # ---------------- GitHub modes ----------------
    if args.git_me:
        if not github_token:
            print("GitHub token not found in cred.conf")
            sys.exit(1)
        all_output = scan_my_repos_and_orgs(github_token)
    elif args.git_other:
        if not args.file:
            print("Error: --git-other requires -f <repos.txt>")
            sys.exit(1)
        all_output = scan_other_repos(args.file)
    elif args.git_profile:
        if not args.file:
            print("Error: --git-profile requires -f <profile.txt>")
            sys.exit(1)
        all_output = scan_profile_repos(args.file, github_token)

    if all_output:
        with open("results.txt", "w") as f:
            f.write("\n".join(all_output))
        if args.output:
            save_to_excel_github("results.txt", args.output)

    # ---------------- Docker modes ----------------
    if args.docker_profile or args.docker_repo:
        if not docker_user or not docker_pass:
            print("Docker credentials not found in cred.conf")
            sys.exit(1)
        token = get_docker_token(docker_user, docker_pass)
        if args.docker_profile:
            with open(args.docker_profile, "r") as f:
                profile_url = f.read().strip()
            username = get_username_from_url(profile_url)
            repos = list_repositories(username, token)
            repos = [f"{username}/{r}" for r in repos]
        else:
            with open(args.docker_repo, "r") as f:
                repos = [line.strip() for line in f if line.strip()]

        with open("image.txt", "w") as out:
            for repo in repos:
                out.write(f"{repo}\n")
        print(f"Saved {len(repos)} repositories to image.txt")

        for full_repo in repos:
            print(f"\n[+] Scanning repository: {full_repo}")
            if args.all_tag:
                for tag in get_container_tags(full_repo):
                    tag_name = tag["name"]
                    if skip_tag(tag_name):
                        continue
                    for img in tag.get("images", []):
                        digest = img["digest"]
                        image_digest = f"{full_repo}@{digest}"
                        findings = scan_with_trufflehog(image_digest)
                        for f in findings:
                            docker_findings.append(parse_docker_finding(full_repo, f))
                        sleep(0.5)
            else:
                image = f"{full_repo}:latest"
                findings = scan_with_trufflehog(image)
                for f in findings:
                    docker_findings.append(parse_docker_finding(full_repo, f))

        if args.output:
            save_to_excel_docker(docker_findings, args.output)

if __name__ == "__main__":
    main()


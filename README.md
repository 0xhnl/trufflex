# trufflex

Trufflex is an all-in-one secret scanning tool that detects sensitive information in GitHub repositories and Docker images using TruffleHog. It automates scanning for personal repositories, organization repositories, public profiles, and Docker Hub repositories, exporting results to Excel for easy analysis.

# Features

- Scan your GitHub repositories and organization repositories with a token.
- Scan other GitHub repositories listed in a file.
- Scan all repositories from GitHub profiles.
- Scan Docker Hub repositories from a profile or repository list.
- Optionally scan all Docker image tags or only the latest tag.
- Exports all findings to Excel (.xlsx) for easy reporting.
- Supports raw TruffleHog output for advanced analysis.

# Requirements

- Python 3.10+
- requests
- pandas
- openpyxl
- trufflehog installed and in $PATH

Install dependencies:

```bash
pip3 install requests pandas openpyxl trufflehog
```

# Setup

- Clone this repository:

```bash
git clone https://github.com/0xhnl/trufflex.git
cd Trufflex
```

- Create a cred.conf file in the root directory with your credentials:

```bash
github:
   - <your_github_token>
docker:
   - <docker_username:docker_password>
```

# Usage

- Scan your own GitHub repos & orgs:

```bash
python3 trufflex.py --git-me -o output.xlsx
```

- Scan other GitHub repos from a list:

```bash
python3 trufflex.py --git-other -f repos.txt -o output.xlsx
```

- Scan all repositories from GitHub profiles:

```bash
python3 trufflex.py --git-profile -f profile.txt -o output.xlsx
```

- Scan all repositories under a Docker Hub profile:

```bash
python3 trufflex.py --docker-profile docker_profile.txt -o docker_results.xlsx
```

- Add `--all-tag` flag to scan all tags:

```bash
python3 trufflex.py --docker-repo docker_repos.txt --all-tag -o docker_results.xlsx
```

- Scan specific Docker repositories:

```bash
python3 trufflex.py --docker-repo docker_repos.txt -o docker_results.xlsx
```

# Output

- GitHub scans:
  - personal.txt – your repositories
  - org.txt – your organizations
  - results.txt – raw TruffleHog JSON
  - output.xlsx – parsed Excel results

- Docker scans:
  - image.txt – scanned images
  - output.xlsx – parsed Excel results
 
# Acknowledgements

- Scanning Git for Secrets guide: https://trufflesecurity.com/blog/scanning-git-for-secrets-the-2024-comprehensive-guide
- Docker tags & architecture scanning: https://trufflesecurity.com/blog/scan-every-tag-and-architecture-of-a-docker-image-for-secrets

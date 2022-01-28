from argparse import ArgumentParser, Namespace

from pandas import DataFrame
from progress.bar import Bar
from requests import Response, get, post


def get_argparse() -> Namespace:
    parser: ArgumentParser = ArgumentParser(
        prog="SSL Metrics GitHub Repository Information",
        usage="Gather information about a GitHub from the GitHub GraphQL API",
    )
    parser.add_argument(
        "-r",
        "--repository",
        help="A specific repository to be analyzed. Must be in format OWNER/REPO",
        type=str,
        required=False,
        default=None,
    )
    parser.add_argument(
        "--topic",
        help="Topic to scrape (up to) the top 1000 repositories from",
        type=str,
        required=False,
        default=None,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="JSON file to dump data to",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-t",
        "--token",
        help="GitHub personal access token",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--min-stars",
        help="Minimum number of stars a repository must have",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "--max-stars",
        help="Maximum number of stars a repository must have",
        type=int,
        required=False,
        default=1000000000,
    )
    parser.add_argument(
        "--min-commits",
        help="Minimum number of commits a repository must have",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "--max-commits",
        help="Maximum number of commits a repository must have",
        type=int,
        required=False,
        default=1000000000,
    )
    parser.add_argument(
        "--min-issues",
        help="Minimum number of issues a repository must have",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "--max-issues",
        help="Maximum number of issues a repository must have",
        type=int,
        required=False,
        default=1000000000,
    )
    parser.add_argument(
        "--min-pull-requests",
        help="Minimum number of pull requests a repository must have",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "--max-pull-requests",
        help="Maximum number of pull requests a repository must have",
        type=int,
        required=False,
        default=1000000000,
    )
    parser.add_argument(
        "--min-forks",
        help="Minimum number of forks a repository must have",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "--max-forks",
        help="Maximum number of forks a repository must have",
        type=int,
        required=False,
        default=1000000000,
    )
    parser.add_argument(
        "--min-watchers",
        help="Minimum number of watchers a repository must have",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "--max-watchers",
        help="Maximum number of watchers a repository must have",
        type=int,
        required=False,
        default=1000000000,
    )

    return parser.parse_args()


def callREST(
    maxStars: int, minStars: int, topic: str, token: str, page: int = 1
) -> Response:
    apiURL: str = f"https://api.github.com/search/repositories?q=stars:{minStars}..{maxStars}+topic:{topic}&sort=stars&per_page=100&page={page}"
    requestHeaders: dict = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ssl-metrics-github-repository-information",
        "Authorization": f"token {token}",
    }

    return get(url=apiURL, headers=requestHeaders)


def callGraphQL(owner: str, repo: str, token: str, verbose: bool = True) -> Response:
    if verbose:
        print(f"Getting information on {owner}/{repo}")

    apiURL: str = f"https://api.github.com/graphql"
    requestHeaders: dict = {
        "Authorization": f"bearer {token}",
    }
    query: str = (
        '{repository(owner: "'
        + owner
        + '", name: "'
        + repo
        + """") {
        ... on Repository {
            owner {
                login
            }
            name
            url
            repositoryTopics(first: 100) {
                totalCount
                nodes {
                    topic {
                        name
                        }
                    }
                }
            object(expression: "HEAD") {
                ... on Commit {
                    history {
                        totalCount
                        }
                    }
                }
            issues {
                totalCount
                }
            pullRequests {
                totalCount
            }
            stargazerCount
            forkCount
            watchers {
                totalCount
            }
            licenseInfo {
                name
                pseudoLicense
            }
        }
    }
}"""
    )

    json: dict = {"query": query, "variables": ""}

    return post(url=apiURL, headers=requestHeaders, json=json)


def flattenJSON(
    json: dict,
    df: DataFrame,
    minCommits: int,
    maxCommits: int,
    minIssues: int,
    maxIssues: int,
    minPullRequests: int,
    maxPullRequests: int,
    minForks: int,
    maxForks: int,
    minWatchers: int,
    maxWatchers: int,
) -> DataFrame:

    root: dict = json["data"]["repository"]

    data: list = [
        root["owner"]["login"],
        root["name"],
        root["url"],
        root["repositoryTopics"]["totalCount"],
        ",".join([x["topic"]["name"] for x in root["repositoryTopics"]["nodes"]]),
        root["stargazerCount"],
    ]

    commits: int = root["object"]["history"]["totalCount"]
    issues: int = root["issues"]["totalCount"]
    pullRequests: int = root["pullRequests"]["totalCount"]
    forks: int = root["forkCount"]
    watchers: int = root["watchers"]["totalCount"]

    if (commits >= minCommits) and (commits <= maxCommits):
        data.append(commits)
    else:
        return df

    if (issues >= minIssues) and (issues <= maxIssues):
        data.append(issues)
    else:
        return df

    if (pullRequests >= minPullRequests) and (pullRequests <= maxPullRequests):
        data.append(pullRequests)
    else:
        return df

    if (forks >= minForks) and (forks <= maxForks):
        data.append(forks)
    else:
        return df

    if (watchers >= minWatchers) and (watchers <= maxWatchers):
        data.append(watchers)
    else:
        return df

    try:
        data.append(root["licenseInfo"]["name"])
        data.append(root["licenseInfo"]["pseudoLicense"])
    except TypeError:
        data.append(None)
        data.append(False)

    df.loc[len(df)] = data

    return df


def main() -> None:
    args: Namespace = get_argparse()

    if (args.repository is None) and (args.topic is None):
        print("Input either a repository or a topic to analyze")
        quit(1)

    if (args.repository is not None) and (args.topic is not None):
        print("Input either a repository or a topic to analyze")
        quit(2)

    if args.output[-5::] != ".json":
        print("Invalid output file type. Output file must be JSON")
        quit(3)

    columns: list = [
        "owner",
        "repository",
        "url",
        "topicCount",
        "topics",
        "stargazerCount",
        "totalCommits",
        "totalIssues",
        "totalPullRequests",
        "forkCount",
        "watchers",
        "licenseName",
        "isPseudoLicense",
    ]
    df: DataFrame = DataFrame(columns=columns)

    if args.topic is None:
        splitRepository: list = args.repository.split("/")
        owner: str = splitRepository[0]
        repo: str = splitRepository[1]

        response: Response = callGraphQL(owner=owner, repo=repo, token=args.token)
        json = response.json()

        flat: DataFrame = flattenJSON(json=json, df=df)

    else:
        currentPage: int = 1
        with Bar(
            message=f"Getting repositories from topic {args.topic}", max=1000
        ) as bar:
            while True:
                resp: Response = callREST(
                    maxStars=args.max_stars,
                    minStars=args.min_stars,
                    topic=args.topic,
                    token=args.token,
                    page=currentPage,
                )

                json: dict = resp.json()

                bar.max = json["total_count"]

                for item in json["items"]:
                    expectedRowCount: int = df.shape[0] + 1

                    owner: str = item["owner"]["login"]
                    repo: str = item["name"]

                    graphQLResponse: Response = callGraphQL(
                        owner=owner, repo=repo, token=args.token, verbose=False
                    )
                    graphQLJSON: dict = graphQLResponse.json()

                    flat: DataFrame = flattenJSON(
                        json=graphQLJSON,
                        df=df,
                        minCommits=args.min_commits,
                        maxCommits=args.max_commits,
                        minIssues=args.min_issues,
                        maxIssues=args.max_issues,
                        minPullRequests=args.min_pull_requests,
                        maxPullRequests=args.max_pull_requests,
                        minForks=args.min_forks,
                        maxForks=args.max_forks,
                        minWatchers=args.min_watchers,
                        maxWatchers=args.max_watchers,
                    )
                    actualRowCount: int = df.shape[0]
                    rowCountDifference: int = expectedRowCount - actualRowCount
                    if rowCountDifference == 0:
                        bar.next()
                    else:
                        bar.max = bar.max - rowCountDifference

                try:
                    lastPage: dict = resp.links["last"]
                except KeyError:
                    break
                else:
                    currentPage += 1

    flat.T.to_json(args.output)


if __name__ == "__main__":
    main()

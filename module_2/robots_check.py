from urllib import robotparser

agent = "cs_scraper"
url = "https://www.thegradcafe.com/"

parser = robotparser.RobotFileParser(url)
parser.set_url(f"{url}robots.txt")
parser.read()

paths = [
    "/",
    "/survey/",
    "/result/",
]

for path in paths:
    print(f"{parser.can_fetch(agent, path), path}")

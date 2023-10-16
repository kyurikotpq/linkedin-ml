"""
Visit a profile and scrape:
- randomly sampled posts and post metrics
"""

# Imports
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import numpy as np

# Config
from config import PROFILES_CSV, SCRAPED_CSV_FILE_PATH, NUM_POSTS_SCRAPE, NUM_POSTS_VIEW, MAX_TRIES, SCROLL_PAUSE_TIME, ACTIVITY_URL, BROWSER_PROFILE

# Elements by XPaths or Classes
ELEMENTS = {
    "followers": (By.XPATH, '//*[contains(@class, "pv-recent-activity-top-card__extra-info")]/div/*[2]'),
    "post_container": (By.XPATH, '//*[contains(@class, "artdeco-card")]'),

    # Rel. to ELEMENTS["post_container"]
    "post_content": (By.XPATH, './/*[contains(@class, "feed-shared-update-v2__description")]'),
    "post_engagement_count": (By.XPATH, './/*[contains(@class, "social-details-social-counts__social-proof-fallback-number") or contains(@class, "social-details-social-counts__reactions-count")]'),

    "post_comment_count": (By.XPATH, './/button[contains(@aria-label, "comment")]/span'),
}


def scroll_until_num_posts_shown(driver, num_posts_view):
    """
    Keep scrolling down until `num_posts` posts
    are visible for us to spy on

    Parameters
    ----------
    - (WebDriver) driver: The WebDriver
    - (int) num_posts_view: Number of posts to be shown

    Returns
    -------
    Boolean indicating success or failure
    """

    # Get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")

    all_posts = driver.find_elements(
        ELEMENTS["post_container"][0], ELEMENTS["post_container"][1])

    while len(all_posts) < num_posts_view:
        # Scroll down to bottom
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")

        # Wait to load page
        time.sleep(SCROLL_PAUSE_TIME)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")

        all_posts = driver.find_elements(
            ELEMENTS["post_container"][0], ELEMENTS["post_container"][1])

        if new_height == last_height:
            break

        last_height = new_height

    return all_posts


def get_post_data(driver, all_posts, num_posts_scrape):
    """
    Randomly sample which posts to scrape, then
    get the metrics for each randomly sampled post

    Parameters
    ----------
    - (int) num_posts_view: Number of posts shown
    - (int) num_posts_scrape: Number of posts to scrape

    Returns
    -------
    list(tuple) where each tuple contains (content, engagement, comments)
    """

    # Store scraped posts and their indices
    scraped_posts = []
    posts_indices = []
    blacklisted_indices = []

    tries = 0
    num_posts_view = len(all_posts) - 1

    # Scrape posts
    while len(scraped_posts) < num_posts_scrape and tries < MAX_TRIES:
        # Randomly sample which posts to scrape
        index = np.random.randint(0, num_posts_view)

        # Make sure posts are unique!
        while index in posts_indices or index in blacklisted_indices:
            index = np.random.randint(0, num_posts_view)
            tries += 1

        # Get the post metrics
        current_post = all_posts[index]
        print("--- --- --- --- --- ---")
        print("Post selected! Index", index)

        try:
            driver.execute_script(
                "arguments[0].scrollIntoView();", current_post)
            time.sleep(SCROLL_PAUSE_TIME * 1.5)

            post_content = ""
            try:
                post_content = str(current_post.find_element(
                    ELEMENTS["post_content"][0], ELEMENTS["post_content"][1]).text)

                post_content = post_content.replace("…see more", "")
                print("-> Post content:", post_content[:40])
            except:
                blacklisted_indices.append(index)
                continue

            driver.execute_script(
                "window.scrollBy(0, arguments[0]);", current_post.size['height'] * 0.9)
            time.sleep(SCROLL_PAUSE_TIME * 1.5)

            # We won't always have comments, e.g. reposts
            post_comment_count = 0
            try:
                post_comment_count = current_post.find_element(
                    ELEMENTS["post_comment_count"][0], ELEMENTS["post_comment_count"][1]).text[0]
                print("-> Post comment count:", post_comment_count)
            except:
                pass

            # We won't always have reactions, e.g. reposts
            post_engagement_count = 0
            try:
                post_engagement_count = current_post.find_element(
                    ELEMENTS["post_engagement_count"][0], ELEMENTS["post_engagement_count"][1]).text
                print("-> Post engagement count:", post_engagement_count)
            except:
                pass

            scraped_posts.append((
                post_content,
                int(post_engagement_count),
                int(post_comment_count),
            ))

            posts_indices.append(index)
            print("Successfully scraped post. Current Total:", len(scraped_posts))
        except Exception as e:
            blacklisted_indices.append(index)

    return scraped_posts


if __name__ == "__main__":
    ff_options = webdriver.FirefoxOptions()
    ff_options.add_argument("-profile")
    ff_options.add_argument(BROWSER_PROFILE)
    driver = webdriver.Firefox(options=ff_options)
    driver.implicitly_wait(SCROLL_PAUSE_TIME * 4)

    # Get the profiles
    urls = pd.read_csv(PROFILES_CSV)["profile_url"]
    POSTS_COLUMNS = ["content", "engagement", "comments"]
    df = pd.DataFrame([], columns=POSTS_COLUMNS)

    for url in urls:
        print("-----------------")
        print("Visiting profile:", url)
        driver.get(url + ACTIVITY_URL)

        follower_count = driver.find_element(
            ELEMENTS["followers"][0], ELEMENTS["followers"][1])

        all_posts = scroll_until_num_posts_shown(driver, NUM_POSTS_VIEW)

        scraped_posts = get_post_data(driver, all_posts, NUM_POSTS_SCRAPE)

        print(len(scraped_posts), "posts scraped for ", url)

        scraped_posts_df = pd.DataFrame(
            scraped_posts, columns=POSTS_COLUMNS)

        df = pd.concat([df, scraped_posts_df], ignore_index=True)
        removed_duplicates_df = df[df['content'].duplicated() == False]

    print("Total posts scraped:", df.shape[0])
    print("Total posts (without duplicates):", removed_duplicates_df.shape[0])
    removed_duplicates_df.to_csv(SCRAPED_CSV_FILE_PATH, index=False)

    driver.quit()

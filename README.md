# Reproducible Locator Break Dataset (RLBD)

### Usage

#### Requirements
* Python
* Git CLI
* Docker and docker-compose
* Make

#### Config
The [Config](config.py) contains all settings regarding the repo
* OUTPUT_PATH: Folder where the outputs will be placed
* REPOS_PATH: Folder where the repositories will be stored
* LB_PATH: Location of the locator break database
* REPRODUCTION_PATH: Location of reproduction files
* START_WITH_CLEAN_DB: If true, each run will generate a new database, if false it will extend the db in the output folder
* DELETE_REPO_AFTER_ANALYZE: If true, will delete each repo after processing
* CREATE_OVERVIEW: If true, will generate a CSV overview
* SAVE_TO_DB: If true, will save results to db
* REPO_LIST: List of repositories used for dataset

#### Create Dataset
The file [create_dataset.py](create_dataset.py) is used to create the dataset of locator changes

#### Create Reproduction
The file [create_reproductible_dataset.py](create_reproudcible_dataset.py) is used to check for reproducible locator breaks.
Under REPRODUCTION_PATH create a folder called repos, containing another folder named after the repository you want to reproduce.
In this folder place all files to reproduce locator breaks. This should atleast include a Makefile with the following targets:
* start: should start the application
* test: should start all the tests and provide a way to only start the tests of a single file
* stop: should stop all services
* setup-e2e: should provide all steps to setup the gui tests, like installing dependencies
After setting up the files the function can be called with the full repository name and a ready_message, which is a log message of the started application, which signals the application is ready

#### Extending the reproduction
A set of reproduction files may not be enough to reproduce all locator changes of all commits in a repo.
For this there is the extend_reproduction function. After changing the files, which were placed in the folder before, call this function to check the remaining locator changes.
This can be repeated till every locator change is reproducible

#### Save Reproduction results
After iterating through locator changes, there will be many reproduction result folders.
The file [save_reproduction.py](save_reproduction.py)  contains the store_reproduction_in_db function which will parse the reproduction files and store each in the database.

#### Reproducing locator breaks
The file [reproduce.py](reproduce.py) can be run through a terminal to reproduce locator breaks.

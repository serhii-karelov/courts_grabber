### Grabber of Ukranian courts

Dependencies:
- python2.7
- beautifulsoup4

How to use:

    $ virtualenv --python=/usr/bin/python2.7 court_grabber
    $ workon court_grabber
    (court_grabber)$ pip install beautifulsoup4
    (court_grabber)$ python grab_courts.py [file_name]

**Note:** by default, name of output file is *courts.csv*
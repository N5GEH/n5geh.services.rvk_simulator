import sys

import platform_mockup as platform


def main():
    PL = platform.DummyPlatform('./config.json')
    PL.main()


if __name__ == '__main__':
    sys.exit(main())

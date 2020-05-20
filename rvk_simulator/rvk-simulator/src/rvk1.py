import sys

import gateway


def main():
    GW = gateway.GatewaySystem(10.0)
    GW.main()


if __name__ == '__main__':
    sys.exit(main())

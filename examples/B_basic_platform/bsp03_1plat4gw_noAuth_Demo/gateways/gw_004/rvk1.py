import sys
import argparse

import gateway


#def main():
def main(argv):
    sys.argv = argv
    parser = argparse.ArgumentParser(description='Virtual gateway')
    parser.add_argument('--conf', type=str, help='configuration file path for the gateway')
    args = parser.parse_args()

    #if len(argv) == 1:
    #    parser.print_help()
    #    return 2

    if not args.conf:
        #print('No configuration file has been provided. Data generation is not possible.')
        conf = "./config.json"
    else:
        conf = args.conf

    GW = gateway.GatewaySystem(10.0)
    GW.main(conf)


if __name__ == '__main__':
    #sys.exit(main())
    sys.exit(main(argv=sys.argv))
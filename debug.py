import argparse

from pprint import pprint

import opc

STRANDS = 5
LENGTH  = 60

def parse_args():
    parser = argparse.ArgumentParser(description='Test Individual LEDs')
    parser.add_argument('-s', '--set', type=int, nargs=3, metavar='VAL', help='Set [STRAND] [LED] to [VALUE]')
    args = parser.parse_args()

    return args

def get_number(prompt, low, high):
    while True:
        value = input(prompt).lower()
        if not value.strip():
            return None

        try:
            if value.startswith('0x'):
                value = int(value, 16)
            else:
                value = int(value)
        except ValueError:
            print("ERROR: Invalid number")
            continue

        if low <= value <= high:
            return value
        else:
            print(f"ERROR: Must be blank line or {low}-{high}")


def main(args):
    client = opc.Client('localhost:7890')
    strands = [[(0, 0, 0)] * LENGTH for _ in range(STRANDS)]

    def display(strand, led, value):
        color = (value, value, value)
        print(f"Setting strand-{strand} LED {led} to {color}")
        strands[strand][led] = (value, value, value)
        
        # Twice to defeat temporal dithering.
        client.put_pixels(sum(strands, []))
        client.put_pixels(sum(strands, []))

    if args.set is not None:
        strand, led, value = args.set
        assert 0 <= strand < STRANDS
        assert 0 <= led < LENGTH
        assert 0 <= value < 256

        display(strand, led, value)
    else:
        print("[Interactive Mode]: Enter blank to quit")
        print("=======================================")
        while True:
            print()
            strand = get_number("Strand Number:", 0, STRANDS - 1)
            if strand is None:
                print("Done")
                break

            led = get_number("LED Number:", 0, LENGTH - 1)
            if led is None:
                print()
                continue

            value = get_number("LED Value:", 0, 255)
            if value is None:
                print()
                continue
            display(strand, led, value)

if __name__ == '__main__':
    try:
        main(parse_args())
    except KeyboardInterrupt:
        pass

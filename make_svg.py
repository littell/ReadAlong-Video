









if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render a ReadAlongs TEI to an SVG animation')
    parser.add_argument('input', type=str, help='Input TEI file')
    parser.add_argument('input', type=str, help='Input SMIL file')
    parser.add_argument('output', type=str, help='Output SVG file')
    args = parser.parse_args()
    main(args.input, args.output)

def main():
    import runez

    from portable_python.cli import main

    runez.click.protected_main(main)


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    import sys
    if "--smoke" in sys.argv:
        import traceback
        from pathlib import Path
        from easything.smoke import run
        report = Path(sys.argv[sys.argv.index("--smoke") + 1])
        try:
            run()
            report.write_text("PASS: packaged EasyThing smoke checks", encoding="utf-8")
        except BaseException:
            report.write_text(traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1)
    else:
        from easything.app import main
        raise SystemExit(main())

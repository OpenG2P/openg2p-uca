#!/usr/bin/env python3

from openg2p_uca.app import Initializer

main_init = Initializer()

app = main_init.return_app()

if __name__ == "__main__":
    main_init.main()

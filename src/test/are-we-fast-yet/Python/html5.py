"""Wrapper script for testing the performance of the html5lib HTML 5 parser.

The input data is the spec document for HTML 5, written in HTML 5.
The spec was pulled from http://svn.whatwg.org/webapps/index.
"""
import io
import os.path

import html5lib

__author__ = "collinwinter@google.com (Collin Winter)"


def bench_html5lib(html_file):
    # html_file.seek(0)
    print(dir(html5lib))
    # html5lib.parse(html_file)


from benchmark import Benchmark



class Html5Lib(Benchmark):
    def inner_benchmark_loop(self, inner_iterations):
        filename = os.path.join(os.path.dirname(__file__),
                            "data", "w3_tr_html5.html")
        # Get all our IO over with early.
        with open(filename, "rb") as fp:
            html_file = io.BytesIO(fp.read())
        for _ in range(inner_iterations):
            bench_html5lib(html_file)
        return True

    def benchmark(self):
        raise Exception("should never be reached")

    def verify_result(self, result):
        raise Exception("should never be reached")

    
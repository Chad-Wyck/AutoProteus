from pathlib import Path
import sys,tempfile,tracemalloc,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_runtime import Deadline,verify_unchanged_bytes


class ByteComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_root=Path(__file__).resolve().parents[1]/'.data/test-weight-editor-bytes'
        cls.temp_root.mkdir(parents=True,exist_ok=True)

    def test_allow_only_declared_span_and_detect_headers_tail(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b';original=bytes(range(256))*64;a.write_bytes(original)
            edited=bytearray(original);edited[200:210]=b'x'*10;b.write_bytes(edited)
            result=verify_unchanged_bytes(a,b,[(200,10)],Deadline(5),chunk_bytes=127)
            self.assertEqual(result['compared_bytes'],len(original)-10)
            for position in (0,199,210,len(original)-1):
                broken=edited.copy();broken[position]^=1;b.write_bytes(broken)
                with self.assertRaises(ValueError):verify_unchanged_bytes(a,b,[(200,10)],Deadline(5))

    def test_layout_guards(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b';a.write_bytes(b'a'*100);b.write_bytes(b'a'*100)
            for regions in [[(-1,1)],[(1,0)],[(99,2)],[(1,5),(4,5)]]:
                with self.assertRaises(ValueError):verify_unchanged_bytes(a,b,regions,Deadline(5))
            with self.assertRaises(ValueError):verify_unchanged_bytes(a,a,[],Deadline(5))
            b.write_bytes(b'a'*101)
            with self.assertRaises(ValueError):verify_unchanged_bytes(a,b,[],Deadline(5))

    def test_streaming_memory_and_deadline(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            for p in (a,b):
                with p.open('wb') as f:
                    for _ in range(256):f.write(b'a'*65536)
            tracemalloc.start()
            try:
                verify_unchanged_bytes(a,b,[],Deadline(5),chunk_bytes=65536)
                self.assertLess(tracemalloc.get_traced_memory()[1],3*65536+32768)
            finally:tracemalloc.stop()
            with self.assertRaises(TimeoutError):verify_unchanged_bytes(a,b,[],Deadline(end=0))

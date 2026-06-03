import conftest
from xime.core.container import XimeContainer
import test_01_scanner
import test_02_happy_path
import test_03_protocol
import test_04_errors


def test1():
    test_01_scanner.test_scanner_finds_concrete_classes()
    test_01_scanner.test_scanner_excludes_protocols()
    test_01_scanner.test_scanner_no_duplicates_across_packages()
    test_01_scanner.test_scanner_skips_class_with_missing_hint()
    print("All tests 1 passed!")

def test2():
    container = XimeContainer().scan("sample.service", "sample.repository").build()
    test_02_happy_path.test_get_service_with_dependency(container)
    test_02_happy_path.test_get_service_without_dependency(container)
    test_02_happy_path.test_dependency_is_injected(container)
    test_02_happy_path.test_service_works_end_to_end(container)
    test_02_happy_path.test_singleton_same_instance(container)
    test_02_happy_path.test_singleton_dependency_shared(container)
    print("All tests 2 passed!")



def test3():
    test_03_protocol.test_protocol_resolved_to_implementation()
    test_03_protocol.test_service_calls_through_correct_implementation()
    test_03_protocol.test_protocol_binding_singleton()
    test_03_protocol.test_swap_implementation()
    print("All tests 3 passed!")


def test4():
    test_04_errors.test_circular_dependency_two_nodes()
    test_04_errors.test_circular_dependency_three_nodes()
    test_04_errors.test_self_dependency()
    test_04_errors.test_missing_implementation_no_candidates()
    test_04_errors.test_missing_implementation_one_candidate_no_binding()
    test_04_errors.test_multiple_implementations_no_binding()
    test_04_errors.test_binding_impl_missing_method()
    test_04_errors.test_binding_with_complete_impl_passes()
    print("All tests 4 passed!")

if __name__ == "__main__":
    test1()
    test2()
    test3()
    test4()
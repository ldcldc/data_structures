"""사용법
python3 check.py                                      최근 수정한 C 파일 채점
python3 check.py Data-Structures/Linked_List/Q2_A_LL.c  지정한 C 파일 채점
python3 check.py --all                                전체 C 파일 채점
python3 check.py --list                               테스트 목록 확인
python3 check.py --timeout 5                          테스트당 제한 시간 5초 (기본 3초)
"""

from __future__ import annotations

import argparse
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / 'Data-Structures'
OUTPUT_LIMIT = 1024 * 1024


@dataclass(frozen=True)
class Check:
    label: str
    expected: str


@dataclass(frozen=True)
class TestCase:
    name: str
    reference: str
    action: str
    stdin: str
    checks: tuple[Check, ...]


def lines(*tokens) -> str:
    return '\n'.join(map(str, tokens)) + '\n'


def inserts(values, menu=1) -> list:
    return [token for value in values for token in (menu, value)]


def values_text(values) -> str:
    return ' '.join(map(str, values))


def node(value, left=None, right=None):
    return (value, left, right)


def tree_tokens(tree) -> list:
    if tree is None:
        return ['a']
    result = [tree[0]]

    def children(current):
        result.extend(child[0] if child else 'a' for child in current[1:])
        for child in current[1:]:
            if child:
                children(child)

    children(tree)
    return result


LL = 'Linked_List'
SQ = 'Stack_and_Queue'
BT = 'Binary_Tree'
BST = 'Binary_Search_Tree'
SUFFIX = {LL: 'A_LL', SQ: 'C_SQ', BT: 'E_BT', BST: 'F_BST'}
PDF = {LL: 'Linked Lists Questions.pdf', SQ: 'Stack and Queues Questions.pdf',
       BT: 'Binary Trees Questions.pdf', BST: 'Binary Search Trees Questions.pdf'}
TESTS: dict[str, list[TestCase]] = {}


def add(section, question, name, pages, action, tokens, *checks, extra=False):
    key = f'{section}/Q{question}_{SUFFIX[section]}.c'
    source = f'{PDF[section]} p.{pages}, Q{question}'
    if extra:
        source += ' 요구사항 기반 추가 검사'
    TESTS.setdefault(key, []).append(TestCase(
        name.removeprefix('PDF '), source, action, lines(*tokens), tuple(Check(*check) for check in checks)))


def build_tests():
    sorted_label = 'The resulting sorted linked list is:'
    for initial, value, index, expected in [
        ([2, 3, 5, 7, 9], 8, 4, [2, 3, 5, 7, 8, 9]),
        ([5, 7, 9, 11, 15], 7, -1, [5, 7, 9, 11, 15]),
    ]:
        add(LL, 1, f'PDF 정렬 삽입 {value}', '1', f'{initial}에 {value} 삽입',
            [*inserts(initial), 1, value, 2, 3, 0],
            (f'The value {value} was added at index', str(index)),
            (sorted_label, values_text(expected)))
    sequence = [2, 3, 5, 7, 9, 8]
    checks = []
    for i in range(1, len(sequence) + 1):
        checks.append(('The resulting linked list is:', values_text(sorted(sequence[:i]))))
    checks += [('The value 8 was added at index', '4'),
               (sorted_label, '2 3 5 7 8 9'),
               ('The resulting linked list is:', '2 3 5 7 8 9'),
               ('The value 5 was added at index', '-1'),
               (sorted_label, '2 3 5 7 8 9'),
               ('The resulting linked list is:', '2 3 5 7 8 9 11'),
               ('The value 11 was added at index', '6'),
               (sorted_label, '2 3 5 7 8 9 11')]
    add(LL, 1, 'PDF 연속 실행 전체', '1–2', '삽입 → 출력 → 중복 삽입 → 출력 → 11 삽입',
        [*inserts(sequence), 2, 3, 1, 5, 2, 3, 1, 11, 2, 3, 0], *checks)
    for initial, value in [([], 0), ([2, 4], 1), ([2, 4], 5), ([2, 4], 2), ([-3, 0, 5], -2)]:
        expected = sorted(set([*initial, value]))
        index = -1 if value in initial else expected.index(value)
        add(LL, 1, f'경계: {initial} + {value}', '1', f'{initial}에 {value} 삽입',
            [*inserts(initial), 1, value, 2, 3, 0],
            (f'The value {value} was added at index', str(index)),
            (sorted_label, values_text(expected)), extra=True)

    for first, second, merged, rest in [
        ([1, 2, 3], [4, 5, 6, 7], [1, 4, 2, 5, 3, 6], [7]),
        ([1, 5, 7, 3, 9, 11], [6, 10, 2, 4], [1, 6, 5, 10, 7, 2, 3, 4, 9, 11], []),
    ]:
        add(LL, 2, f'PDF 교차 병합 ({len(first)}, {len(second)})', '2–3',
            f'{first}와 {second} 병합', [*inserts(first), *inserts(second, 2), 3, 0],
            ('The resulting linked list 1:', values_text(merged)),
            ('The resulting linked list 2:', values_text(rest)))

    odd_inputs = [[2, 3, 4, 7, 15, 18], [2, 7, 18, 3, 4, 15], [1, 3, 5], [2, 4, 6]]
    for question, parity, word, page in [(3, 1, 'odd', '3'), (4, 0, 'even', '4')]:
        label = f'The resulting linked list after moving {word} integers to the back of the linked list is:'
        for values in odd_inputs + [[1], [2], [-3, 0, -2, 1]]:
            expected = [x for x in values if x % 2 != parity] + [x for x in values if x % 2 == parity]
            add(LL, question, f'{word} 이동: {values}', page, f'{values}의 {word} 노드를 뒤로 이동',
                [*inserts(values), 2, 0], (label, values_text(expected)), extra=values not in odd_inputs)

    for values in [[2, 3, 5, 6, 7], [1, 2], [1, 2, 3, 4], [-2, 0, 3]]:
        split = (len(values) + 1) // 2
        add(LL, 5, f'앞/뒤 분할: {values}', '4–5', f'{values}를 앞/뒤로 분할',
            [*inserts(values), 2, 0],
            ('Front linked list:', values_text(values[:split])),
            ('Back linked list:', values_text(values[split:])), extra=len(values) != 5)

    for values in [[30, 20, 40, 70, 50], [9, 2, 1], [1, 2, 9], [7], [-5, -1, -3]]:
        index = values.index(max(values))
        expected = [values[index], *values[:index], *values[index + 1:]]
        add(LL, 6, f'최대 노드 이동: {values}', '5–6', f'{values}의 최댓값을 앞으로 이동',
            [*inserts(values), 2, 0], ('The resulting linked list after moving largest stored value to the front of the list is:', values_text(expected)),
            extra=len(values) != 5)
    for values in [[1, 2, 3, 4, 5], [1], [1, 2], [-1, 0, -1, 3]]:
        add(LL, 7, f'재귀 역순: {values}', '6', f'{values}를 역순으로 변환',
            [*inserts(values), 2, 0],
            ('The resulting linked list after reversed the given linked list is:', values_text(values[::-1])),
            extra=len(values) != 5)

    for question, values, kind in [(1, [1, 2, 3, 4, 5], 'queue'), (2, [1, 3, 5, 6, 7], 'stack')]:
        label = f'The resulting {kind} is:'
        for data in [values, [7], [-1, 0, -1, 2]]:
            expected = data if question == 1 else data[::-1]
            add(SQ, question, f'{kind} 생성: {data}', '1', f'{data}로 {kind} 생성',
                [*inserts(data), 2, 0], (label, values_text(expected)), extra=data != values)
        expected = values if question == 1 else values[::-1]
        changed = [*values, 9] if question == 1 else [9, *values[::-1]]
        add(SQ, question, f'기존 {kind}를 비우고 재생성', '1', '생성 → 재생성 → 9 추가 → 재생성',
            [*inserts(values), 2, 2, 1, 9, 2, 0],
            (label, values_text(expected)), (label, values_text(expected)),
            (label, values_text(changed)), extra=True)

    pairs = [([16, 15, 11, 10, 5, 4], True), ([16, 15, 11, 10, 5, 1], False),
             ([16, 15, 11, 10, 5], False), ([1], False), ([1, 2], True),
             ([2, 2], False), ([-2, -1, 0, 1], True), ([9, 1, 3, 4], False)]
    for i, (values, valid) in enumerate(pairs):
        add(SQ, 3, f'쌍별 연속: {values}', '1–2', f'top부터 {values} 검사',
            [*inserts(values[::-1]), 2, 0],
            ('The stack is', 'pairwise consecutive' if valid else 'not pairwise consecutive'), extra=i >= 3)

    for question, label in [(4, 'The resulting queue after reversing its elements is:'),
                            (5, 'The resulting reversed queue is:')]:
        for values in [[1, 2, 3, 4, 5], [1], [1, 2], [-2, 0, 3, -2]]:
            add(SQ, question, f'큐 역순: {values}', '2', f'{values}를 역순으로 변환',
                [*inserts(values), 2, 0], (label, values_text(values[::-1])), extra=len(values) != 5)
    for i, (values, target, expected) in enumerate([
        ([1, 2, 3, 4, 5, 6, 7], 4, [4, 5, 6, 7]),
        ([10, 20, 15, 25, 5], 15, [15, 25, 5]),
        ([1, 2, 3], 1, [1, 2, 3]), ([1, 2, 3], 3, [3]),
        ([2, 1, 2, 3], 2, [2, 1, 2, 3]), ([7], 7, [7]),
    ]):
        add(SQ, 6, f'{target}까지 제거: {values}', '2', f'top부터 {values}, 선택값 {target}',
            [*inserts(values[::-1]), 2, target, 0],
            ('The resulting stack after removing values until the given value:', values_text(expected)), extra=i >= 2)
    expressions = [('()', True), ('([])', True), ('{[]()[]}', True), ('{{)]', False),
                   ('[({{)])', False), ('(', False), (')', False), ('([)]', False),
                   ('()[]{}', True), ('((()))', True), ('())', False)]
    for i, (expression, valid) in enumerate(expressions):
        add(SQ, 7, f'괄호: {expression}', '2–3', f'{expression}의 괄호 균형 검사',
            [1, expression, 2, 0], ('', 'balanced!' if valid else 'not balanced!'), extra=i >= 5)

    identical_tree = node(5, node(3, node(1), node(2)), node(7, node(4), node(8)))
    height_tree = node(4, node(2, node(1), node(3)), node(6, node(5), node(7)))
    one_child = node(50, node(20, node(10), node(30, node(55))), node(60, None, node(80)))
    odd_tree = node(50, node(40, node(11), node(35)), node(60, node(80), node(85)))
    mirror = node(4, node(5, None, node(6)), node(2, node(3), node(1)))
    general = node(50, node(30, node(25), node(65)), node(60, node(10), node(75)))
    great = node(50, node(30, node(25), node(65, node(20))),
                 node(60, node(10), node(75, None, node(15))))
    for i, (first, second, same) in enumerate([
        (identical_tree, identical_tree, True), (None, None, True),
        (node(1), None, False), (None, node(1), False), (node(1), node(2), False),
        (node(1, node(2)), node(1, None, node(2)), False),
        (node(1, node(2)), node(1, node(3)), False),
    ]):
        add(BT, 1, ['값과 구조가 같은 두 트리', '두 트리 모두 비어 있음', '둘째 트리만 비어 있음',
             '첫째 트리만 비어 있음', '구조는 같고 값이 다름', '좌우 자식 위치가 다름',
             '자식 노드의 값이 다름'][i], '1–2', f'두 트리 비교: {first} / {second}',
            [1, *tree_tokens(first), 2, *tree_tokens(second), 3, 0],
            ('Both trees are', 'structurally identical.' if same else 'different.'), extra=i > 0)
    tree_cases = {
        2: [('PDF 높이', height_tree, '2'), ('빈 트리', None, '-1'), ('단일 노드', node(8), '0'),
            ('왼쪽 사슬', node(1, node(2, node(3, node(4)))), '3'),
            ('오른쪽 사슬', node(1, None, node(2, None, node(3))), '2')],
        3: [('PDF 자식 하나', one_child, '2'), ('빈 트리', None, '0'), ('단일 노드', node(8), '0'),
            ('완전 트리', height_tree, '0'), ('한쪽 사슬', node(1, node(2, node(3))), '2')],
        4: [('PDF 홀수 합', odd_tree, '131.'), ('빈 트리', None, '0.'),
            ('음수 홀수', node(-3, node(-5), node(2)), '-8.'),
            ('모두 짝수', node(2, node(4), node(6)), '0.'), ('단일 홀수', node(7), '7.')],
        5: [('PDF 반전', mirror, '1 2 3 4 6 5'), ('빈 트리', None, ''),
            ('단일 노드', node(8), '8'), ('한쪽 사슬', node(1, node(2, node(3))), '1 2 3')],
        7: [('PDF 최솟값', general, '10'), ('단일 노드', node(8), '8'),
            ('오른쪽 최솟값', node(3, node(2), node(-5)), '-5'),
            ('루트 최솟값', node(-7, node(2), node(3)), '-7')],
        8: [('PDF 증손자', great, '50'), ('빈 트리', None, ''), ('단일 노드', node(8), ''),
            ('증손자 없음', height_tree, ''),
            ('왼쪽 깊이 4', node(10, node(5, node(3, node(1)))), '10'),
            ('오른쪽 깊이 4', node(10, None, node(5, None, node(3, None, node(1)))), '10')],
    }
    tree_labels = {2: 'The maximum height of the binary tree is:',
                   3: 'The number of nodes that have exactly one child node is:',
                   4: 'The sum of all odd numbers in the binary tree is:',
                   5: 'Mirror binary tree is:', 7: 'Smallest value of the binary tree is:',
                   8: 'The values stored in all nodes of the tree that has at least one great-grandchild are:'}
    tree_pages = {2: '2–3', 3: '3–4', 4: '4–5', 5: '5–6', 7: '7–8', 8: '8–9'}
    for question, cases in tree_cases.items():
        for i, (name, tree, expected) in enumerate(cases):
            add(BT, question, name, tree_pages[question], f'트리: {tree}',
                [1, *tree_tokens(tree), 2, 0], (tree_labels[question], expected), extra=i > 0)
    for i, (tree, limit, expected) in enumerate([
        (general, 55, '50 30 25 10'), (general, 10, ''),
        (general, 50, '30 25 10'), (general, 100, '50 30 25 65 60 10 75'),
        (node(-1, node(-3), node(2)), 0, '-1 -3'), (None, 5, ''),
    ]):
        add(BT, 6, f'{limit}보다 작은 값', '6–7', f'트리 {tree}에서 {limit} 미만 출력',
            [1, *tree_tokens(tree), 2, limit, 0],
            (f'The values smaller than {limit} are:', expected), extra=i > 0)

    sample = [20, 15, 50, 10, 18, 25, 80]
    for question, kind, values, expected, page in [
        (1, 'level-order', sample, '20 15 50 10 18 25 80', '1'),
        (2, 'in-order', [20, 15, 50, 10, 18], '10 15 18 20 50', '1'),
        (3, 'pre-order', sample, '20 15 10 18 50 25 80', '2'),
        (4, 'post-order', sample, '10 18 15 25 80 50 20', '2'),
        (5, 'post-order', sample, '10 18 15 25 80 50 20', '2–3'),
    ]:
        label = f'The resulting {kind} traversal of the binary search tree is:'
        add(BST, question, f'PDF {kind}', page, f'{values} 삽입 후 순회',
            [*inserts(values), 2, 0], (label, expected))
        for data in [[], [7], [1, 2, 3, 4], [4, 3, 2, 1]]:
            if kind == 'in-order':
                result = sorted(data)
            elif kind == 'post-order':
                result = data[::-1]
            else:
                result = data
            add(BST, question, f'경계 {kind}: {data}', page, f'{data} 삽입 후 순회',
                [*inserts(data), 2, 0], (label, values_text(result)), extra=True)
        add(BST, question, '같은 트리 두 번 순회', page, f'{values} 삽입 후 두 번 순회',
            [*inserts(values), 2, 2, 0], (label, expected), (label, expected), extra=True)


build_tests()


def normalise(text: str) -> str:
    return ' '.join(text.split())


def result_value(text: str) -> str:
    value = normalise(text)
    if value.lower() == 'empty':
        return ''
    if re.fullmatch(r'[+-]?\d+(?:\s+[+-]?\d+)*\.?', value):
        return ' '.join(str(int(token)) for token in value.removesuffix('.').split())
    if value in ('pairwise consecutive.', 'not pairwise consecutive.'):
        return value[:-1]
    return value


def label_pattern(label: str) -> str:
    return r'\s+'.join(re.escape(word) for word in label.split())


def extract_results(output: str, checks: tuple[Check, ...]) -> list[tuple[str, str]]:
    labels = sorted({check.label for check in checks if check.label}, key=len, reverse=True)
    patterns = [f'(?P<L{i}>{label_pattern(label)})(?!:)' for i, label in enumerate(labels)]
    if any(not check.label for check in checks):
        patterns.append(r'(?:^|:\s*|\n)(?P<sentence>(?:not[ \t]+)?balanced!)[ \t]*(?=\r?\n|$)')
    if not patterns:
        return []
    matches = list(re.finditer('|'.join(patterns), output))
    results = []
    for i, match in enumerate(matches):
        if match.lastgroup == 'sentence':
            results.append(('', result_value(match.group('sentence'))))
            continue
        label = labels[int(match.lastgroup[1:])]
        end = matches[i + 1].start() if i + 1 < len(matches) else len(output)
        remainder = output[match.end():end]
        remainder = re.split(r'Please input your choice[^\n:]*:', remainder, maxsplit=1)[0]
        results.append((label, result_value(remainder)))
    return results


@dataclass(frozen=True)
class RunResult:
    stdout: str
    stderr: str
    error: str = ''


def run_program(executable: Path, stdin: str, timeout: float) -> RunResult:
    with tempfile.TemporaryFile() as input_file, tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        input_file.write(stdin.encode())
        input_file.seek(0)
        try:
            process = subprocess.Popen([str(executable)], stdin=input_file, stdout=output, stderr=errors, cwd=ROOT)
        except OSError as exc:
            return RunResult('', '', str(exc))
        deadline = time.monotonic() + timeout
        problem = ''
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    problem = f'시간 초과: {timeout:g}초 안에 종료되지 않았습니다.'
                    break
                if output.tell() + errors.tell() > OUTPUT_LIMIT:
                    problem = '출력 제한 초과: 1 MiB'
                    break
                time.sleep(0.01)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
        if not problem and output.tell() + errors.tell() > OUTPUT_LIMIT:
            problem = '출력 제한 초과: 1 MiB'
        if not problem and process.returncode:
            if process.returncode < 0:
                problem = f'비정상 종료: {signal.Signals(-process.returncode).name}'
            else:
                problem = f'비정상 종료: 종료 코드 {process.returncode}'
        output.seek(0)
        errors.seek(0)
        return RunResult(output.read(OUTPUT_LIMIT).decode(errors='replace'),
                         errors.read(OUTPUT_LIMIT).decode(errors='replace'), problem)


def compile_source(source: Path, executable: Path) -> tuple[bool, str]:
    compiler = shutil.which('clang') or shutil.which('gcc') or shutil.which('cc')
    if compiler is None:
        return False, 'C 컴파일러(clang/gcc/cc)를 찾지 못했습니다.'
    try:
        result = subprocess.run(
            [compiler, '-std=c11', '-w', '-g', str(source), '-o', str(executable)],
            capture_output=True, text=True, errors='replace', cwd=ROOT, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def grade_case(executable: Path, case: TestCase, timeout=3.0) -> bool:
    run = run_program(executable, case.stdin, timeout)
    actual = extract_results(run.stdout, case.checks)
    expected = [(check.label, result_value(check.expected)) for check in case.checks]
    passed = not run.error and actual == expected
    print(f'  [{"성공" if passed else "실패"}] {case.name}')
    if passed:
        return True
    for i in range(max(len(expected), len(actual))):
        wanted = expected[i] if i < len(expected) else None
        got = actual[i] if i < len(actual) else None
        if wanted == got:
            continue
        if wanted is not None and got is not None and wanted[0] == got[0]:
            expected_text = wanted[1] or '(빈 출력)'
            actual_text = got[1] or '(빈 출력)'
        else:
            expected_text = normalise(' '.join(wanted)) if wanted is not None else '(추가 출력 없어야 함)'
            actual_text = normalise(' '.join(got)) if got is not None else '(결과 출력 없음)'
        if len(expected) > 1 or len(actual) > 1:
            print(f'    {i + 1}번째 결과')
        print(f'    기대: {expected_text}')
        print(f'    실제: {actual_text}')
    if run.error:
        print(f'    오류: {run.error}')
    if run.stderr:
        print(run.stderr.rstrip())
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', nargs='?', type=Path, help='채점할 C 파일')
    parser.add_argument('--all', action='store_true', help='모든 C 파일 채점')
    parser.add_argument('--list', action='store_true', help='테스트 목록만 출력')
    parser.add_argument('--timeout', type=float, default=3.0, help='테스트당 제한 시간 (기본 3초)')
    args = parser.parse_args()
    if args.source and args.all:
        parser.error('source와 --all은 함께 사용할 수 없습니다.')
    if not 0 < args.timeout < float('inf'):
        parser.error('--timeout은 유한한 양수여야 합니다.')
    if args.list:
        for key, cases in TESTS.items():
            print(f'{key}: {len(cases)}개')
            for case in cases:
                print(f'  {case.name} [{case.reference}]')
        print(f'총 {len(TESTS)}개 파일, {sum(map(len, TESTS.values()))}개 테스트')
        return 0
    files = sorted(SOURCE_ROOT.rglob('*.c'))
    if args.source:
        sources = [(ROOT / args.source).resolve()]
    elif args.all:
        sources = files
    elif files:
        sources = [max(files, key=lambda path: path.stat().st_mtime)]
    else:
        sources = []
    if not sources:
        print(f'C 파일이 없습니다: {SOURCE_ROOT}')
        return 2
    passed = total = successful_files = 0
    configuration_error = False
    for source in sources:
        try:
            key = source.resolve().relative_to(SOURCE_ROOT.resolve()).as_posix()
        except ValueError:
            print(f'지원하지 않는 경로: {source}')
            configuration_error = True
            continue
        if not source.is_file() or key not in TESTS:
            print(f'파일 또는 등록된 테스트가 없습니다: {source}')
            configuration_error = True
            continue
        cases = TESTS[key]
        total += len(cases)
        print(f'\n{key} ({len(cases)}개 테스트)', flush=True)
        with tempfile.TemporaryDirectory(prefix='c_grader_') as directory:
            executable = Path(directory) / 'program'
            ok, log = compile_source(source, executable)
            if not ok and log:
                print(f'  [컴파일 실패]\n{log}')
            if not ok:
                if not log:
                    print('  [컴파일 실패] 컴파일러의 오류 출력이 없습니다.')
                print(f'  결과: 컴파일 실패로 {len(cases)}개 테스트 실행 못 함')
                continue
            file_passed = sum(grade_case(executable, case, args.timeout) for case in cases)
            passed += file_passed
            successful_files += file_passed == len(cases)
            print(f'  결과: {file_passed}/{len(cases)} 성공', flush=True)
    print(f'\n전체 결과: 파일 {successful_files}/{len(sources)} 성공, 테스트 {passed}/{total} 성공')
    return 2 if configuration_error else (0 if passed == total else 1)


if __name__ == '__main__':
    raise SystemExit(main())

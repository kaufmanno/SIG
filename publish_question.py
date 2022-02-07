import glob
import os
import nbformat
import codecs
import sys
import subprocess


verbose = True
mode = 'standard'


def add_file_into_commit(filename, branch='question'):
    assert_on_branch(branch)
    if verbose:
        print(f'Adding {filename} to commit on branch {branch}...')
        proceed()
    execute(f'git add {filename}')


def assert_on_branch(branch):
    out = subprocess.check_output('git rev-parse --abbrev-ref HEAD', shell=True)
    if out.decode('utf-8').lower().strip('\n') != branch:
        print(f'Warning: You should be on branch {branch}. You\'re currently on {out.decode("utf-8")}. Quitting...')
        exit(1)


def checkout_to_branch(branch='questions'):
    if verbose:
        print(f'Checking out to a new local branch {branch}...')
        proceed()
    execute(f'git checkout -b {branch}')


def clean_path(current_course, branch='questions'):
    assert_on_branch(branch)
    if verbose:
        print(f'Moving tools to {current_course} on branch {branch}...')
        proceed()
    execute(f'git mv tools/* ./{current_course}')
    if verbose:
        print(f'Moving files from {current_course}...')
        proceed()
    execute('find . -maxdepth 1 -type f -exec git rm {} \\;')
    # TODO: remove subdirectories related to the other courses
    execute(f'git mv ./{current_course}/.gitignore .')
    execute(f'git mv ./{current_course}/* .')
    if verbose:
        print(f'Removing {current_course} emptied subdirectory...')
        proceed()
    execute(f'rm -rf ./{current_course}')


def commit_changes(message=None, branch='questions'):
    assert_on_branch(branch)
    if verbose:
        print(f'Committing changes to {branch}...')
        proceed()
    if message is None:
        message = f'Undisclosed updates'
    execute(f'git commit -m "{message}"')


def confirm(question, default_answer='No'):
    reply = input(f'{question}? [{default_answer}] > ')
    if reply == '':
        reply = default_answer
    return reply.lower()


def create_question(notebook):
    out_notebook = get_question_filename(notebook)

    if verbose:
        print(f'Converting {notebook}...')
        proceed()

    nb = nbformat.read(notebook, nbformat.NO_CONVERT)

    # outputs = None
    solution = None
    cells_to_keep = []
    question_nr = 0
    reveal = 0
    section = 0
    subsection = 0
    for i in nb['cells']:
        source = i['source']
        # print(f'\n_______\nSTART\n_______\n{i}')
        if i['cell_type'] == 'code':
            if '# @manage_solutions' in source:
                if solution is not None:
                    cells_to_keep.append(solution)
                    solution = None
                # code = i['source']
                code = "# @info: Exécutez-moi pour activer les questions interactives\n" \
                       "# -----------------------------------------------------------\n\n" \
                       "from IPython.display import HTML\nimport codecs\n\n# @hidden\n" \
                       "HTML('''\n<script>\ncode_show=true;\nfunction code_toggle() {\n if (code_show){\n" \
                       "  $('.cm-comment:contains(@hidden)').closest('div.input').hide();\n } else {\n" \
                       "  $('.cm-comment:contains(@hidden)').closest('div.input').show();\n }\n" \
                       " code_show = !code_show\n}\n" \
                       "$( document ).ready(code_toggle);\n</script>\n" \
                       "<div># @info: Exécutez-moi pour activer les questions interactives </div>\n''')"
                i['source'] = code
                i['outputs'] = [nbformat.notebooknode.NotebookNode({'name': 'stdout', 'output_type': 'stream',
                                                                    'text': '# @info: Exécutez-moi pour cacher le'  
                                                                            ' code, puis sauvegardez le notebook\n'})]
                cells_to_keep.append(i)

            elif '# @solution' in source:
                if '@reveal' in source:
                    if solution is not None:
                        cells_to_keep.append(solution)
                        solution = None
                    code = source.replace('# @solution', '').replace('@reveal', '').replace('@keep_output', '').replace(
                        '\n', '<br>\n').lstrip()
                    while code.startswith('<br>\n'):
                        code = code[5:]

                    s = f"""<div class=\"alert alert-block alert-warning\">\n\tSi vous être bloqué(e),
                    affichez une solution en pressant sur le bouton ci-dessous.<br>\n\tVeillez à <b>comprendre</b> la solution
                    et à la tester par vous-même.\n</div> <br>\n\n<button data-toggle=\"collapse\" data-target=\"#reveal_{reveal:04d}">
                    Afficher le code</button>\n<div id="reveal_{reveal:04d}" class="collapse">\n<br><code>{code}\n</code>\n</div>\n
                    """
                    sx = codecs.encode(codecs.encode(s, 'utf8'), 'hex')
                    i['source'] = f"# @hidden\nsx={sx}\nHTML(codecs.decode(codecs.decode(sx,'hex'), 'utf8'))"
                    # i.pop('execution_count')
                    outputs = i.pop('outputs')
                    # i['cell_type'] = 'raw'
                    i['outputs'] = [nbformat.notebooknode.NotebookNode({'name': 'stdout', 'output_type': 'stream',
                                                                        'text': "# @info: Exécutez-moi pour accéder à l'aide interactive\n"})]
                    cells_to_keep.append(i)
                    reveal += 1
                    if '@keep_output' in source:
                        solution = nbformat.v4.new_code_cell(source='# Résultat attendu ci-dessous...', outputs=outputs)
                        solution.pop('id')
                        cells_to_keep.append(solution)
                        solution = None
                else:
                    i.source = ''
                    if '@keep_output' in source:
                        if solution is not None:
                            cells_to_keep.append(solution)
                            solution = None
                        solution = nbformat.v4.new_code_cell(source='# Résultat attendu ci-dessous...',
                                                             outputs=i['outputs'])
                        solution.pop('id')
                        cells_to_keep.append(solution)
                        solution = None
                    else:
                        i.outputs = []
                        solution = i
            else:
                if solution is not None:
                    solution['outputs'] = []
                    cells_to_keep.append(solution)
                    solution = None
                cells_to_keep.append(i)
        elif i['cell_type'] == 'markdown':
            if '### @question\n' in source:
                if solution is not None:
                    cells_to_keep.append(solution)
                solution = None
                qa = source.rsplit('### @answer\n')
                question = qa[0].strip('### @question\n')
                if verbose:
                    print(f'question {question} found in cell {i["execution_count"]}')
                if len(qa) > 1:
                    answer = qa[1]
                    s = f"""<div class="alert alert-block alert-warning">\n<b>Question: </b><br>{question}\n</div> <br>\n<button data-toggle="collapse"
                    data-target="#question_{question_nr:04d}">Afficher la réponse</button>\n\n<div id="question_{question_nr:04d}"
                    class="collapse">{answer}\n</div>\n"""
                    sx = codecs.encode(codecs.encode(s, 'utf8'), 'hex')
                    i['source'] = f"# @hidden\nsx={sx}\nHTML(codecs.decode(codecs.decode(sx,'hex'), 'utf8'))"
                    i['cell_type'] = 'code'
                    i['execution_count'] = None
                    i['outputs'] = [nbformat.notebooknode.NotebookNode({'name': 'stdout', 'output_type': 'stream',
                                                                        'text': '# @info: Exécutez-moi pour afficher la question interactive\n'})]
                else:
                    s = f"""<div class="alert alert-block alert-warning">\n<b>Question: </b><br>{question}\n</div>"""
                    i['source'] = s

                cells_to_keep.append(i)
                question_nr += 1
            elif '### @info' in source:
                info = source.replace('### @info', '').replace('\n', '<br>\n').lstrip()
                while info.startswith('<br>\n'):
                    info = info[5:]
                i['source'] = f'<div class="alert alert-block alert-info">\n<b>Info:</b> {info}\n</div>'
                cells_to_keep.append(i)
            elif '### @warning' in source:
                warning = source.replace('### @warning', '').replace('\n', '<br>\n').lstrip()
                while warning.startswith('<br>\n'):
                    warning = warning[5:]
                i['source'] = f'<div class="alert alert-block alert-warning">\n<b>Attention:</b><br> {warning}\n</div>'
                cells_to_keep.append(i)
            elif '### @note' in source:
                note = source.replace('### @note', '').replace('\n', '<br>\n').lstrip()
                while note.startswith('<br>\n'):
                    note = info[5:]
                i['source'] = f'<b>Note:</b><br>{note}\n'
                cells_to_keep.append(i)
            elif "## @section" in source:
                section += 1
                if solution is not None:
                    cells_to_keep.append(solution)
                solution = None
                i['source'] = '***\n'
                title = source.split(' | ', 1)[1]
                i['source'] += f'## {section}. {title}'
                cells_to_keep.append(i)
                subsection = 0
            elif "### @subsection" in source:
                subsection += 1
                if solution is not None:
                    cells_to_keep.append(solution)
                solution = None
                logo_html = None
                if "@r_code" in source:
                    logo_html = '<img align="right" src="http://localhost:8888/kernelspecs/ir/logo-64x64.png" width="24"/>'
                elif "@python_code" in source:
                    logo_html = '<img align="right" src="http://localhost:8888/kernelspecs/python3/logo-64x64.png" width="24"/>'
                i['source'] = '<div class="alert alert-block alert-success">\n'
                if logo_html is not None:
                    i['source'] += '\t'
                    i['source'] += logo_html
                title = source.split(' | ', 1)[1]
                i['source'] += '\t'
                i['source'] += f'<b>{section}.{subsection} {title}</b>'
                i['source'] += '\n</div>'
                cells_to_keep.append(i)
            else:
                if solution is not None:
                    solution['outputs'] = []
                    cells_to_keep.append(solution)
                    solution = None
                cells_to_keep.append(i)
        else:
            if solution is not None:
                solution['outputs'] = []
                cells_to_keep.append(solution)
                solution = None
            cells_to_keep.append(i)

    if solution is not None:
        cells_to_keep.append(solution)
        # print(f'\n_______\nEND\n_______\n{cells_to_keep[-1]}')
    nb['cells'] = cells_to_keep

    nbformat.write(nb, out_notebook, version=nbformat.NO_CONVERT)
    return out_notebook


def proceed(ask=False):
    if (mode == 'debug' or ask) and confirm('Proceed', 'Yes') != 'yes':
        exit("Interrupted by user...")


def execute(cmd, shell=True):
    out = subprocess.check_output(cmd, shell=shell)
    if verbose:
        print(out.decode('utf-8'))


def get_question_filename(notebook):
    if '_Solution' in notebook:
        out_notebook = notebook.split('_Solution')[0] + notebook.split('_Solution')[1]
    else:
        print(f'Warning: _Solution not found in notebook name {notebook}. Quitting...')
        out_notebook = ''
        exit(1)
    return out_notebook


def pull_repo(repo, branch='main'):
    if repo == '':
        branch = ''
    if verbose:
        print(f'Pulling from {repo} {branch}...')
        proceed()
    cmd = 'git pull'
    if repo != '':
        cmd += f' {repo} {branch}'
    execute(cmd)


def push_changes(repo='', branch='questions', remote_branch='main'):
    assert_on_branch(branch)
    if verbose:
        if repo == '':
            print(f'Pushing ...')
        else:
            print(f'Pushing to {repo} {branch}:{remote_branch}...')
        proceed()
    cmd = 'git push'
    if repo != '':
        cmd += f' {repo} {branch}:{remote_branch}'
    execute(cmd)


def push_repo_and_remove_branch(repo, branch='questions', remote_branch='main'):
    push_changes(repo, branch, remote_branch)
    if verbose:
        print(f'Stashing changes...')
        proceed()
    execute('git stash')
    if verbose:
        print(f'Checking out back to master...')
        proceed()
    execute('git checkout master')
    if verbose:
        print(f'Deleting {branch} branch...')
        proceed()
    if branch in ['master', 'main']:
        reply = confirm(f'DO YOU REALLY WANT TO ERASE THE {branch.capitalize()} BRANCH', 'No')
        if reply != 'yes':
            exit('Interrupted by user...')
    execute(f'git branch -D {branch}')


def remove_file(filename, branch='questions'):
    assert_on_branch(branch)
    if verbose:
        print(f'Removing file {filename} from branch {branch}...')
        proceed()
    execute(f'git rm -f {filename}')


def remove_solutions(parent_dir='.', branch='questions'):
    to_remove = glob.glob(f'{parent_dir}/**/*_Solution.ipynb', recursive=True)

    assert_on_branch(branch)
    if verbose:
        print('Removing solution files...')
        proceed()
    for f in to_remove:
        execute(f'git rm -f {f}')


def track_files(dirname='.'):
    files_in_dir = glob.glob(os.path.join(dirname, '*'))
    files_in_dir = [os.path.basename(i) for i in files_in_dir]
    track_file = os.path.join(dirname, 'track.txt')
    if os.path.exists(track_file):
        with open(track_file, 'r') as file:
            files_to_track = file.readlines()
            files_to_track = [i.strip('\n') for i in files_to_track]
    else:
        files_to_track = []
    for i in files_in_dir:
        if i not in files_to_track:
            untrack_file(i)


def untrack_file(filename, branch='questions'):
    assert_on_branch(branch)
    if verbose:
        print(f'Untracking file {filename} on branch {branch}...')
        proceed()
    execute(f'git rm --cached {filename}')


if __name__ == '__main__':
    # TODO: Add more courses with corresponding subdirectories and github folders in the list
    course_list = ['SIG']

    assert_on_branch('master')
    repository = None

    if verbose:
        print('Starting...')

    # Read command line arguments : course section topic [mode]
    course = sys.argv[1]
    section = sys.argv[2]
    topic = sys.argv[3]
    if len(sys.argv) > 4:
        mode = sys.argv[4]
    if mode == 'debug':
        verbose = True

    # Constructs the solution filename from the arguments
    solution_filename = f'./{course}/{section}/{topic}/{topic}_Solution.ipynb'

    # Sets the repository
    questions_repo = f'git@github.com:kaufmanno/{course}.git'

    if verbose:
        print(f'Updating a question notebook from {solution_filename} in {course}...')

    # Prepares the question notebook creates a new branch synchronize with questions repo on github
    if course in course_list:
        question_filename = create_question(solution_filename)
        msg=f'Check {question_filename}, run the manage solutions cell and save the notebook.'
        print('\n' + '='*(4+len(msg)) + '\n= ' + msg + ' =\n' + '='*(4+len(msg)) + '\n')
        proceed(ask=True)
        add_file_into_commit(question_filename, branch='master')
        add_file_into_commit(solution_filename, branch='master')
        commit_changes(message=f'Updates {question_filename}', branch='master')
        push_changes(branch='master')
        checkout_to_branch('questions')
        clean_path(course, branch='questions')
        solution_filename = f'./{section}/{topic}/{topic}_Solution.ipynb'
        untrack_file(solution_filename, 'questions')
        track_files(dirname=f'./{section}/{topic}')
        commit_changes(f'Updates {question_filename} in {course}', branch='questions')
        pull_repo(questions_repo, branch='main')
        push_repo_and_remove_branch(course)
        assert_on_branch('master')
        print(f'Question successfully updated {topic} question notebook in section {section} of {course}...')
    else:
        print(f'Unknown course {course}')

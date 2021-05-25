import psycopg2
import os
import shutil
import subprocess
import argparse
import logging
import errno
import stat

from datetime import datetime

db_conn = psycopg2.connect(host="localhost", database="qscoreddb", user="postgres", password="postgres")

tag = str(datetime.timestamp(datetime.now()))
working_dir = 'C:/Users/arnas/Desktop/raw/' + tag

repositories_path = '{root}/repos/'.format(root=working_dir)
classes_path = '{root}/classes'.format(root=working_dir)
methods_path = '{root}/methods'.format(root=working_dir)
codesplit_args = ['java', '-Xmx6g', '-jar', 'CodeSplitJava.jar', '-i']

class Smell:
    def __init__(self, type, class_, component, method):
        self.type = type
        self.class_ = class_
        self.component = component
        self.method = method

    def __repr__(self):
        return '/'.join(self.class_, self.method, self.name)

class Repository:
    def __init__(self, solution_id, name, repository_link, upload_date):
        self.solution_id = solution_id
        self.name = name
        self.repository_link = repository_link.replace('https://github.com', 'ssh://git@github.com')
        self.upload_date = upload_date

    def repository_folder(self):
        return os.path.join(repositories_path, self.solution_id)

    def cleanup(self):
        ensure_directory_exists(self.repository_folder())
        ensure_directory_exists(os.path.join(get_absolute_path(classes_path), self.solution_id))
        ensure_directory_exists(os.path.join(get_absolute_path(methods_path), self.solution_id))

    def checkout(self):
        subprocess.run(['git', 'clone', '--single-branch', '{}.git'.format(self.repository_link), self.solution_id], cwd=repositories_path, shell=True, check=True)

        branch = self.execute_git_command(['branch', '--show-current']).decode()

        revision_hash = self.execute_git_command([
            'rev-list',
            '-n', '1',
            '--before="{}"'.format(self.upload_date.strftime("%Y-%m-%d %H:%M:%S")),
            branch
        ]).decode()

        self.execute_git_command(['checkout', revision_hash])

    def execute_git_command(self, args):
        return subprocess.check_output(['git'] + args, cwd=self.repository_folder(), shell=True)

    #for c#
    # def get_solutions(self):
    #    return list(set([get_absolute_path(str(path)) for path in Path(self.repository_folder()).rglob('*.sln')]))

    def split_into_classes(self):
        subprocess.run(codesplit_args + [get_absolute_path(self.repository_folder()), '-m', 'class', '-o', get_absolute_path(classes_path)], shell=True, check=True)

    def split_into_methods(self):
        subprocess.run(codesplit_args + [get_absolute_path(self.repository_folder()), '-m', 'method', '-o', get_absolute_path(methods_path)], shell=True, check=True)

    def split_into_positive_negative(self, smell_name, smell_type, smells):
        root_path = os.path.join(classes_path if smell_type == 'design' else methods_path, self.solution_id)
        smell_path = os.path.join(working_dir, smell_name)
        positive_path = os.path.join(smell_path, 'positive') 
        negative_path = os.path.join(smell_path, 'negative')

        ensure_directory_exists(smell_path, False)
        ensure_directory_exists(positive_path, False)
        ensure_directory_exists(negative_path, False)

        for module in os.listdir(root_path):
            module_path = os.path.join(root_path, module)

            if module not in smells:
                if smell_type == 'design':
                    move_to_path(module_path, '_'.join([self.solution_id, module]), negative_path)
                else:
                    for class_ in os.listdir(module_path):
                        move_to_path(os.path.join(module_path, class_), '_'.join([self.solution_id, module, class_]), negative_path)
                continue

            if smell_type == 'design':
                split_code(module_path, smells[module], '_'.join([self.solution_id, module]), positive_path, negative_path)
            else:
                for class_ in os.listdir(module_path):
                    class_path = os.path.join(module_path, class_)
                    if class_ not in smells[module]:
                        move_to_path(class_path, '_'.join([self.solution_id, module, class_]), negative_path)
                        continue
                    split_code(class_path, smells[module][class_], '_'.join([self.solution_id, module, class_]), positive_path, negative_path)

current_path = os.getcwd()
def get_absolute_path(path):
    return path if os.path.isabs(path) else os.path.join(current_path, path)

def move_to_path(path, file_prefix, target_path):
    for file in os.listdir(path):
        shutil.copy(os.path.join(path, file), os.path.join(target_path, file_prefix + file))

def split_code(path, smells, file_prefix, positive_path, negative_path):
    for code_block in (name.replace('.code', '') for name in os.listdir(path)):
        file_name = code_block + '.code'
        file_path = os.path.join(path, file_name)
        if code_block in smells:
            shutil.copy(file_path, os.path.join(positive_path, '_'.join([file_prefix, file_name])))
        else:
            shutil.copy(file_path, os.path.join(negative_path, '_'.join([file_prefix, file_name])))

def handleRemoveReadonly(func, path, exc):
  excvalue = exc[1]
  if func in (os.rmdir, os.unlink, os.remove) and excvalue.errno == errno.EACCES:
      os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
      func(path)
  else:
      raise

def ensure_directory_exists(path, ensureClear = True):
    if os.path.exists(path):
        if ensureClear:
            shutil.rmtree(path, ignore_errors=False, onerror=handleRemoveReadonly)
        else:
            return
    os.makedirs(path)

def get_smells(solution_id, smell_name):
    cursor = db_conn.cursor()
    cursor.execute('SELECT type, class, component, method from smells WHERE solution_id = %s AND name = %s', (solution_id, smell_name))
    
    rows = cursor.fetchall()

    cursor.close()

    smells = [Smell(row[0], row[1], row[2], row[3]) for row in rows]

    if len(smells) == 0:
        return {}

    if smells[0].type == 'implementation':
        return ('implementation', organise_implementation_smells(smells))

    return ('design', organise_design_smells(smells))

def organise_implementation_smells(smells):
    result = {}

    for smell in smells:
        if smell.component in result:
            if smell.class_ in result[smell.component]:
                result[smell.component][smell.class_].add(smell.method)
            else:
                result[smell.component][smell.class_] = {smell.method}
        else:
            result[smell.component] = {smell.class_: {smell.method}}

    return result

def organise_design_smells(smells):
    result = {}

    for smell in smells:
        if smell.component in result:
            result[smell.component].add(smell.class_)
        else:
            result[smell.component] = {smell.class_}

    return result

def get_repositories(offset, limit):
    cursor = db_conn.cursor()
    cursor.execute('SELECT solution_id, name, repository_link, upload_date FROM solution_smells WHERE "Multifaceted Abstraction" >= 7 AND prog_language = \'java\' ORDER BY name DESC OFFSET {} LIMIT {}'.format(offset, limit))
    
    rows = cursor.fetchall()

    cursor.close()
    return [Repository(row[0], row[1], row[2], row[3]) for row in rows]

ensure_directory_exists(working_dir)
ensure_directory_exists(repositories_path)
ensure_directory_exists(classes_path)
ensure_directory_exists(methods_path)

parser = argparse.ArgumentParser()
parser.add_argument("offset", type=int)
parser.add_argument("limit", type=int)
args = parser.parse_args()

repositories = get_repositories(args.offset, args.limit)

print ('using directory ' + working_dir)

for i, repository in enumerate(repositories):
    print('processing repository {}/{}...'.format(i + 1, len(repositories)))

    try:
        repository.checkout()
        repository.split_into_classes()
        repository.split_into_methods()

        for smell_name in ['Multifaceted Abstraction', 'Magic Number', 'Empty catch clause', 'Complex Method']:
            (smell_type, smells) = get_smells(repository.solution_id, smell_name)
            repository.split_into_positive_negative(smell_name, smell_type, smells)

        repository.cleanup()
    except Exception as Argument:
        logging.exception('Cannot process repository {}, skipping'.format(repository.name))

#0 128
#128 128
#256 128
#384 128
#512 128
#640 130
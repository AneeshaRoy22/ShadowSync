import os
import time
import mysql.connector
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tictactoe import Tic_Tac_Toe


class MyHandler(FileSystemEventHandler):
    def __init__(self, db_connection, disallowed_extensions):
        super().__init__()
        self.db_connection = db_connection
        self.disallowed_extensions = disallowed_extensions

    def is_legitimate_file(self, file_path):
        # Check if the file has a disallowed extension
        file_name = os.path.basename(file_path)
        return any(file_name.lower().endswith(ext.lower()) for ext in self.disallowed_extensions)

    def on_created(self, event):
        file_path = event.src_path
        file_name = os.path.basename(file_path)

        # Check if the file is legitimate based on the allowed_extensions
        if self.is_legitimate_file(file_path):
            print(f'Skipping monitoring for non-legitimate file: {file_name}')
            return

    
        if event.is_directory:
            file_type = "directory"
            # Add an observer for the new subdirectory
            Observer().schedule(MyHandler(self.db_connection), file_path, recursive=True)
            Observer().start()
            
        else:
            file_type = os.path.splitext(file_name)[1]

        date_file_created = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(os.path.getctime(file_path)))

        # Check if the file already exists in the database
        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT fileid FROM files WHERE filepath = %s",
            (file_path,)
        )
        existing_file = cursor.fetchone()

        if existing_file:
            # Mark the previous file entry as deleted
            cursor.execute(
                "UPDATE files SET deleted_y_n = 'Y' WHERE filepath = %s",
                (file_path,)
            )

            cursor.fetchall()

            # Insert a new entry with the updated file name
            cursor.execute(
                "INSERT INTO files (filename, filetype, datefilecreated, datethatfileentereddb, deleted_y_n, filepath) "
                "VALUES (%s, %s, %s, NOW(), 'N', %s)",
                (file_name, file_type, date_file_created, file_path)
            )
        else:
            # Insert information into the database for the new file
            cursor.execute(
                "INSERT INTO files (filename, filetype, datefilecreated, datethatfileentereddb, deleted_y_n, filepath) "
                "VALUES (%s, %s, %s, NOW(), 'N', %s)",
                (file_name, file_type, date_file_created, file_path)
            )

        self.db_connection.commit()
        cursor.close()

        print(f'{file_type} {file_name} has been created or updated in the database.')

    def on_deleted(self, event):
        file_path = event.src_path

        # Mark the file or directory as deleted in the database
        cursor = self.db_connection.cursor()
        cursor.execute(
            "UPDATE files SET deleted_y_n = 'Y' WHERE filepath = %s",
            (file_path,)
        )
        self.db_connection.commit()
        cursor.close()

        print(f'{file_path} has been deleted. Database updated.')

    def on_moved(self, event):
        src_path = event.src_path
        dest_path = event.dest_path

        # Check if the entry already exists in the database
        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT fileid FROM files WHERE filepath = %s",
            (src_path,)
        )
        existing_entry = cursor.fetchone()

        if existing_entry:
            # Add a short delay to allow the move operation to complete
            time.sleep(0.5)

            # Mark the previous entry as deleted
            cursor.execute(
                "UPDATE files SET deleted_y_n = 'Y' WHERE filepath = %s",
                (src_path,)
            )

            # Fetch the result to consume it
            cursor.fetchall()

            # Insert a new entry with the updated name
            if os.path.isdir(dest_path):
                cursor.execute(
                    "INSERT INTO files (filename, filetype, datefilecreated, datethatfileentereddb, deleted_y_n, filepath) "
                    "VALUES (%s, %s, NOW(), NOW(), 'N', %s)",
                    (os.path.basename(dest_path), 'directory', dest_path)
                )
            else:
                cursor.execute(
                    "INSERT INTO files (filename, filetype, datefilecreated, datethatfileentereddb, deleted_y_n, filepath) "
                    "VALUES (%s, %s, NOW(), NOW(), 'N', %s)",
                    (os.path.basename(dest_path), 'file', dest_path)
                )

            self.db_connection.commit()

        cursor.close()

        if os.path.isdir(dest_path):
            print(f'Directory {src_path} has been renamed to {dest_path}. Database updated.')
        else:
            print(f'File {src_path} has been renamed to {dest_path}. Database updated.')

def add_existing_files_and_directories_to_db(directory_path, db_connection):
    cursor = db_connection.cursor()

    for foldername, subfolders, filenames in os.walk(directory_path):
        for item in subfolders + filenames:
            item_path = os.path.join(foldername, item)

            # Check if the file or directory already exists in the database
            cursor.execute(
                "SELECT fileid FROM files WHERE filepath = %s",
                (item_path,)
            )
            existing_entry = cursor.fetchone()

            if not existing_entry:
                # Insert information into the database for the existing file or directory
                item_name = os.path.basename(item_path)
                item_type = "directory" if os.path.isdir(item_path) else os.path.splitext(item_name)[1]
                date_item_created = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(os.path.getctime(item_path)))

                cursor.execute(
                    "INSERT INTO files (filename, filetype, datefilecreated, datethatfileentereddb, deleted_y_n, filepath) "
                    "VALUES (%s, %s, %s, NOW(), 'N', %s)",
                    (item_name, item_type, date_item_created, item_path)
                )

    db_connection.commit()
    cursor.close()

def monitor_directory(directory_path, db_connection):
    # Add information about existing files and directories in the directory to the database
    add_existing_files_and_directories_to_db(directory_path, db_connection)

    event_handler = MyHandler(db_connection, disallowed_extensions)
    observer = Observer()
    observer.schedule(event_handler, directory_path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(60)  # Sleep for 1 minute

    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def run_tic_tac_toe():
    # Create an instance of the Tic-Tac-Toe game
    tic_tac_toe_game = Tic_Tac_Toe()
    print("tictactoe running")
    tic_tac_toe_game.mainloop()

if __name__ == "__main__":

    db_host = "localhost"
    db_user = "root"
    db_password = "root"
    db_name = "shadowsync"

    directory_to_monitor = r"C:\shadow"  # Replace with the path to your directory
    disallowed_extensions = ['.tmp', '.exe', '.bat', '.dll','.bak','.swp','.cache','.temp','.bin']
    
    
    try:
        # Establish a connection to the MySQL database
        db_connection = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name
        )
        print(f"Connected to MySQL database: {db_name}")

        # Create a table if not exists
        cursor = db_connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                fileid INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255),
                filetype VARCHAR(10),
                datefilecreated DATETIME,
                datethatfileentereddb DATETIME,
                deleted_y_n CHAR(1),
                filepath VARCHAR(255)
            )
        """)
        cursor.close()

        print("Table 'files' created or already exists.")

        # Start the file monitoring thread
        file_monitoring_thread = threading.Thread(target=monitor_directory, args=(directory_to_monitor, db_connection))
        file_monitoring_thread.start()

        # Run the Tic-Tac-Toe game in a separate thread
        tic_tac_toe_thread = threading.Thread(target=run_tic_tac_toe)
        tic_tac_toe_thread.start()

        # Wait for both threads to finish
        file_monitoring_thread.join()
        tic_tac_toe_thread.join()

    except mysql.connector.Error as err:
        print(f"Error: {err}")

    finally:
        # Close the database connection when done
        if 'db_connection' in locals() and db_connection.is_connected():
            db_connection.close()
            print("Disconnected from MySQL database.")

import glob

import pandas as pd

from utils.utils import rivals2_plot, rivals2_line_plot


def main():
    # Step 1: Read all CSV files
    file_paths = glob.glob("data/leaderboard_output_*.csv")  # Path to directory where csv files are saved

    if not file_paths:
        print("No files found. Ensure the files are in the correct directory.")
    else:
        # Sort file paths by date (assuming the date is the last part of the filename)
        file_paths.sort(key=lambda x: x.split("_")[-1].replace(".csv", ""))

        # Load all CSVs into a dictionary with dates as keys
        dataframes = {}
        for file_path in file_paths:
            # Extract the date from the file name
            date = file_path.split("_")[-1].replace(".csv", "")
            df = pd.read_csv(file_path)
            df['date'] = date
            dataframes[date] = df

        # Combine all dataframes into one
        combined_df = pd.concat(dataframes.values(), ignore_index=True)

        # Create a pivot table to see scores across dates for each player
        pivot_df = combined_df.pivot_table(index="name", columns="date", values="score", aggfunc="first")

        # Identify players with changed scores
        score_changes = pivot_df.nunique(axis=1) > 1  # Check if a player has more than one unique score

        # Identify players present only in the latest file
        latest_date = max(dataframes.keys())
        latest_scores = dataframes[latest_date].set_index("name")["score"]
        new_players = latest_scores.index.difference(pivot_df.index)

        # Filter the latest file for players with changed scores or new players
        changed_or_new_players = score_changes[score_changes].index.union(new_players)
        result_df = dataframes[latest_date][dataframes[latest_date]["name"].isin(changed_or_new_players)]

        # Prepare the dataframe for output
        result_df = result_df[["name", "score"]]  # Keep only relevant columns

        # Display or use the result dataframe
        print("Filtered dataframe for plotting:")
        print(result_df.head())

        rivals2_plot(result_df,
                     title="Rivals II Rank Distribution (last 7 days)",
                     save_name='rank_distribution_7days.png')
        rivals2_line_plot(result_df,
                          title="Rivals II Player Count by Ranked Score (last 7 days)",
                          save_name='rank_distribution_line_7days.png')


if __name__ == '__main__':
    main()

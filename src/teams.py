from collections import defaultdict
from statistics import mean
from typing import List, NamedTuple

import discord

from src.constants import ROLE_PREFIX


class TeamData(NamedTuple):
    """Stores the TLA, number of members and presence of a team supervisor for a team."""

    TLA: str
    members: int = 0
    leader: bool = False

    def has_leader(self) -> bool:
        """Return whether the team has a leader."""
        return self.leader

    def is_primary(self) -> bool:
        """Return whether the team is a primary team."""
        return not self.TLA[-1].isdigit() or self.TLA[-1] == 1

    def school(self) -> str:
        """TLA without the team number."""
        return ''.join(c for c in self.TLA if c.isalpha())

    def __str__(self) -> str:
        data_str = f'{self.TLA:<15} {self.members:>2}'
        if self.leader is False:
            data_str += '  No supervisor'
        return data_str


class TeamsData(NamedTuple):
    """A container for a list of TeamData objects."""

    teams_data: List[TeamData]

    def gen_team_memberships(self, guild: discord.Guild, leader_role: discord.Role) -> None:
        """Generate a list of TeamData objects for the given guild, stored in teams_data."""
        teams_data = []

        for role in filter(lambda role: role.name.startswith(ROLE_PREFIX), guild.roles):
            team_data = TeamData(
                TLA=role.name[len(ROLE_PREFIX):],
                members=len(list(filter(
                    lambda member: leader_role not in member.roles,
                    role.members,
                ))),
                leader=len(list(filter(
                    lambda member: leader_role in member.roles,
                    role.members,
                ))) > 0,
            )

            teams_data.append(team_data)

        teams_data.sort(key=lambda team: team.TLA)  # sort by TLA
        self.teams_data.clear()
        self.teams_data.extend(teams_data)

    @property
    def empty_tlas(self) -> List[str]:
        """A list of TLAs for teams with no members or supervisors."""
        return [
            team.TLA
            for team in self.teams_data
            if not team.leader and team.members == 0
        ]

    @property
    def missing_leaders(self) -> List[str]:
        """A list of TLAs for teams with no supervisors but at least one member."""
        return [
            team.TLA
            for team in self.teams_data
            if not team.leader and team.members > 0
        ]

    @property
    def leader_only(self) -> List[str]:
        """A list of TLAs for teams with only supervisors and no members."""
        return [
            team.TLA
            for team in self.teams_data
            if team.leader and team.members == 0
        ]

    @property
    def empty_primary_teams(self) -> List[str]:
        """A list of TLAs for primary teams with no members."""
        return [
            team.TLA
            for team in self.teams_data
            if team.is_primary() and team.TLA in self.empty_tlas
        ]

    @property
    def primary_leader_only(self) -> List[str]:
        """A list of TLAs for primary teams with only supervisors."""
        return [
            team.TLA
            for team in self.teams_data
            if team.is_primary() and team.TLA in self.leader_only
        ]

    def team_summary(self) -> str:
        """A summary of the teams."""
        return '\n'.join([
            'Members per team',
            *(
                str(team)
                for team in self.teams_data
            )
        ])

    def warnings(self) -> str:
        """A list of warnings for the teams."""
        return '\n'.join([
            f'Empty teams: {len(self.empty_tlas)}',
            f'Teams without supervisors: {len(self.missing_leaders)}',
            f'Teams with only supervisors: {len(self.leader_only)}',
            '',
            f'Empty primary teams: {len(self.empty_primary_teams)}',
            f'Primary teams with only supervisors: {len(self.primary_leader_only)}',
        ])

    def statistics(self) -> str:
        """A list of statistics for the teams."""
        num_teams: int = len(self.teams_data)
        member_counts = [team.members for team in self.teams_data]
        num_members = sum(member_counts)
        num_schools = len([team for team in self.teams_data if team.is_primary()])

        min_team = min(self.teams_data, key=lambda x: x.members)
        max_team = max(self.teams_data, key=lambda x: x.members)

        school_members = defaultdict(list)
        for team in self.teams_data:
            school_members[team.school()].append(team.members)
        school_avg = {school: mean(members) for school, members in school_members.items()}
        max_avg_school, max_avg_size = max(school_avg.items(), key=lambda x: x[1])

        return '\n'.join([
            f'Total teams: {num_teams}',
            f'Total schools: {num_schools}',
            f'Total students: {num_members}',
            f'Max team size: {max_team.members} ({max_team.TLA})',
            f'Min team size: {min_team.members} ({min_team.TLA})',
            f'Average team size: {mean(member_counts):.1f}',
            f'Average school members: {num_members / num_schools:.1f}',
            f'Max team size, school average: {max_avg_size:.1f} ({max_avg_school})',
        ])

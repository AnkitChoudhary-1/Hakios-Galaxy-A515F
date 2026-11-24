// IrisFeedViewController.m - Full Home feed screen implementation
#import "IrisFeedViewController.h"
#import "IrisTopNavBar.h"
#import "IrisStoriesHeaderView.h"
#import "IrisPostCell.h"
#import "IrisTheme.h"
#import "IrisData.h"
#import "IrisProfileViewController.h"
#import "IrisTabBarController.h"

// Forward declare modal controllers (implemented in subsequent steps)
@interface IrisCommentsViewController : UIViewController
- (instancetype)initWithPost:(IrisPost *)post;
@end

@interface IrisPostViewerViewController : UIViewController
- (instancetype)initWithPost:(IrisPost *)post;
@end

@interface IrisStoryViewerViewController : UIViewController
- (instancetype)initWithStory:(IrisStory *)story;
@end

@interface IrisFeedViewController () <UITableViewDataSource, UITableViewDelegate, IrisTopNavBarDelegate, IrisStoriesHeaderViewDelegate, IrisPostCellDelegate>

@property (nonatomic, strong) IrisTopNavBar *topNavBar;
@property (nonatomic, strong) UITableView *tableView;
@property (nonatomic, strong) IrisStoriesHeaderView *storiesHeaderView;

@end

@implementation IrisFeedViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // 1. Top Navigation Bar
    CGFloat topBarH = 88.0;
    self.topNavBar = [[IrisTopNavBar alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, topBarH)];
    self.topNavBar.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.topNavBar.delegate = self;
    [self.view addSubview:self.topNavBar];
    
    // 2. Table View
    CGRect tableFrame = CGRectMake(0, topBarH, self.view.bounds.size.width, self.view.bounds.size.height - topBarH - 64.0);
    self.tableView = [[UITableView alloc] initWithFrame:tableFrame style:UITableViewStylePlain];
    self.tableView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.tableView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.tableView.separatorStyle = UITableViewCellSeparatorStyleNone;
    self.tableView.dataSource = self;
    self.tableView.delegate = self;
    self.tableView.showsVerticalScrollIndicator = NO;
    
    [self.tableView registerClass:[IrisPostCell class] forCellReuseIdentifier:@"IrisPostCell"];
    
    // 3. Stories Row as Header
    self.storiesHeaderView = [[IrisStoriesHeaderView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, 114.0)];
    self.storiesHeaderView.delegate = self;
    self.tableView.tableHeaderView = self.storiesHeaderView;
    
    [self.view addSubview:self.tableView];
    
    // Listen for theme changes and data reload
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleThemeChanged:)
                                                 name:IrisThemeDidChangeNotification
                                               object:nil];
}

- (void)viewWillAppear:(BOOL)animated {
    [super viewWillAppear:animated];
    [self.tableView reloadData];
    [self.storiesHeaderView reloadStories];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)handleThemeChanged:(NSNotification *)note {
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.tableView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    [self.topNavBar updateTheme];
    [self.storiesHeaderView updateTheme];
    [self.tableView reloadData];
}

#pragma mark - Table View Data Source

- (NSInteger)numberOfSectionsInTableView:(UITableView *)tableView {
    return 1;
}

- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section {
    return [IrisData sharedData].posts.count;
}

- (CGFloat)tableView:(UITableView *)tableView heightForRowAtIndexPath:(NSIndexPath *)indexPath {
    IrisPost *post = [IrisData sharedData].posts[indexPath.row];
    return [IrisPostCell heightForPost:post width:tableView.bounds.size.width];
}

- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    IrisPostCell *cell = [tableView dequeueReusableCellWithIdentifier:@"IrisPostCell" forIndexPath:indexPath];
    cell.delegate = self;
    IrisPost *post = [IrisData sharedData].posts[indexPath.row];
    [cell configureWithPost:post];
    return cell;
}

#pragma mark - IrisTopNavBarDelegate

- (void)topNavBarDidTapThemeToggle {
    [[IrisTheme sharedTheme] toggleTheme];
}

- (void)topNavBarDidTapNotifications {
    // Switch to Activity tab
    if ([self.parentViewController isKindOfClass:[IrisTabBarController class]]) {
        [(IrisTabBarController *)self.parentViewController switchToTab:IrisTabItemActivity];
    }
}

- (void)topNavBarDidTapMessages {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Direct Messages"
                                                                   message:@"Iris Direct Messaging is available in Phase 2.\nStay tuned for end-to-end encrypted chats."
                                                            preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Dismiss" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}

#pragma mark - IrisStoriesHeaderViewDelegate

- (void)storiesHeaderViewDidSelectStory:(IrisStory *)story {
    IrisStoryViewerViewController *viewer = [[IrisStoryViewerViewController alloc] initWithStory:story];
    viewer.modalPresentationStyle = UIModalPresentationFullScreen;
    [self presentViewController:viewer animated:YES completion:nil];
}

#pragma mark - IrisPostCellDelegate

- (void)postCell:(id)cell didTapUser:(NSString *)username {
    IrisProfileViewController *profileVC = [[IrisProfileViewController alloc] initWithUsername:username];
    if (self.navigationController) {
        [self.navigationController pushViewController:profileVC animated:YES];
    } else {
        UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:profileVC];
        nav.modalPresentationStyle = UIModalPresentationFullScreen;
        [self presentViewController:nav animated:YES completion:nil];
    }
}

- (void)postCell:(id)cell didTapMediaForPost:(IrisPost *)post {
    IrisPostViewerViewController *viewer = [[IrisPostViewerViewController alloc] initWithPost:post];
    viewer.modalPresentationStyle = UIModalPresentationFullScreen;
    [self presentViewController:viewer animated:YES completion:nil];
}

- (void)postCell:(id)cell didTapLikeForPost:(IrisPost *)post {
    // Local state updated in cell
}

- (void)postCell:(id)cell didTapCommentForPost:(IrisPost *)post {
    IrisCommentsViewController *commentsVC = [[IrisCommentsViewController alloc] initWithPost:post];
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:commentsVC];
    [self presentViewController:nav animated:YES completion:nil];
}

- (void)postCell:(id)cell didTapShareForPost:(IrisPost *)post {
    UIAlertController *sheet = [UIAlertController alertControllerWithTitle:[NSString stringWithFormat:@"Share post by @%@", post.username]
                                                                   message:nil
                                                            preferredStyle:UIAlertControllerStyleActionSheet];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Copy Share Link" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
        UIPasteboard.generalPasteboard.string = [NSString stringWithFormat:@"https://iris.social/p/%@", post.postId];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Send via Iris Direct" style:UIAlertActionStyleDefault handler:nil]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Share to External..." style:UIAlertActionStyleDefault handler:nil]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:sheet animated:YES completion:nil];
}

- (void)postCell:(id)cell didTapBookmarkForPost:(IrisPost *)post {
    // Local state updated in cell
}

- (void)postCell:(id)cell didTapMoreForPost:(IrisPost *)post {
    UIAlertController *sheet = [UIAlertController alertControllerWithTitle:nil
                                                                   message:nil
                                                            preferredStyle:UIAlertControllerStyleActionSheet];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Share Post" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
        [self postCell:cell didTapShareForPost:post];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Copy Link" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
        UIPasteboard.generalPasteboard.string = [NSString stringWithFormat:@"https://iris.social/p/%@", post.postId];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Mute Posts from User" style:UIAlertActionStyleDestructive handler:nil]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Report Inappropriate Content" style:UIAlertActionStyleDestructive handler:nil]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:sheet animated:YES completion:nil];
}

@end
